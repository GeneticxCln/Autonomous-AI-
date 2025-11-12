"""
Enterprise Data Management and Governance System
Implements data lifecycle management, automated backup/disaster recovery,
data classification, and quality monitoring for enterprise-grade data governance.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import hashlib
import shutil
import os
import sqlite3
import csv
import zipfile
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Set, Union
from enum import Enum
from datetime import datetime, timedelta
import uuid
import schedule
import threading
import pickle
from pathlib import Path

# Database and storage libraries
try:
    import boto3
    import psycopg2
    import redis
    from sqlalchemy import create_engine, text
    STORAGE_AVAILABLE = True
except ImportError:
    STORAGE_AVAILABLE = False

logger = logging.getLogger(__name__)


class DataClassification(Enum):
    """Data classification levels."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_SECRET = "top_secret"


class DataQuality(Enum):
    """Data quality levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


class BackupType(Enum):
    """Types of backup operations."""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    SNAPSHOT = "snapshot"


class DisasterRecoveryTier(Enum):
    """Disaster recovery tiers with RTO/RPO objectives."""
    TIER_0 = "tier_0"  # RTO: <1 min, RPO: <1 min
    TIER_1 = "tier_1"  # RTO: <1 hour, RPO: <1 hour
    TIER_2 = "tier_2"  # RTO: <4 hours, RPO: <24 hours
    TIER_3 = "tier_3"  # RTO: <24 hours, RPO: <1 week
    TIER_4 = "tier_4"  # RTO: <1 week, RPO: <1 month


@dataclass
class DataAsset:
    """Individual data asset definition."""
    asset_id: str
    name: str
    description: str
    data_type: str  # "database", "file_system", "cloud_storage", "application_data"
    classification: DataClassification
    owner: str
    steward: str
    location: str  # "database_name", "file_path", "bucket_name"
    size_bytes: Optional[int] = None
    record_count: Optional[int] = None
    sensitivity_score: int = 0  # 1-10 scale
    retention_period_days: Optional[int] = None
    created_date: float = field(default_factory=time.time)
    last_accessed: Optional[float] = None
    last_modified: Optional[float] = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataQualityRule:
    """Data quality validation rule."""
    rule_id: str
    asset_id: str
    rule_name: str
    rule_type: str  # "completeness", "uniqueness", "accuracy", "validity", "consistency"
    rule_definition: str  # SQL query or validation logic
    severity: str  # "critical", "high", "medium", "low"
    threshold: float  # Expected percentage (e.g., 0.95 for 95%)
    last_executed: Optional[float] = None
    execution_results: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class BackupJob:
    """Backup job definition."""
    job_id: str
    name: str
    asset_id: str
    backup_type: BackupType
    source_location: str
    destination_location: str
    schedule: str  # "daily", "weekly", "monthly", "hourly"
    retention_days: int
    compression_enabled: bool = True
    encryption_enabled: bool = True
    enabled: bool = True
    last_execution: Optional[float] = None
    next_execution: Optional[float] = None
    execution_results: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DisasterRecoveryPlan:
    """Disaster recovery plan definition."""
    plan_id: str
    name: str
    description: str
    dr_tier: DisasterRecoveryTier
    assets: List[str]  # List of asset_ids
    rto_minutes: int  # Recovery Time Objective
    rpo_minutes: int  # Recovery Point Objective
    procedures: List[str]  # Step-by-step procedures
    contacts: List[str]  # Emergency contacts
    testing_schedule: str  # "monthly", "quarterly", "annually"
    last_tested: Optional[float] = None
    test_results: Dict[str, Any] = field(default_factory=dict)


class DataAssetManager:
    """
    Manages enterprise data assets, classification, and metadata.
    """
    
    def __init__(self, database_path: str = "data_governance.db"):
        self.db_path = database_path
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize data governance database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create data assets table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_assets (
                    asset_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    data_type TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    steward TEXT NOT NULL,
                    location TEXT NOT NULL,
                    size_bytes INTEGER,
                    record_count INTEGER,
                    sensitivity_score INTEGER,
                    retention_period_days INTEGER,
                    created_date REAL,
                    last_accessed REAL,
                    last_modified REAL,
                    tags TEXT,
                    metadata TEXT
                )
            """)
            
            # Create data quality rules table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_quality_rules (
                    rule_id TEXT PRIMARY KEY,
                    asset_id TEXT NOT NULL,
                    rule_name TEXT NOT NULL,
                    rule_type TEXT NOT NULL,
                    rule_definition TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    threshold REAL NOT NULL,
                    last_executed REAL,
                    execution_results TEXT,
                    enabled BOOLEAN DEFAULT 1,
                    FOREIGN KEY (asset_id) REFERENCES data_assets (asset_id)
                )
            """)
            
            # Create backup jobs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backup_jobs (
                    job_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    backup_type TEXT NOT NULL,
                    source_location TEXT NOT NULL,
                    destination_location TEXT NOT NULL,
                    schedule TEXT NOT NULL,
                    retention_days INTEGER NOT NULL,
                    compression_enabled BOOLEAN DEFAULT 1,
                    encryption_enabled BOOLEAN DEFAULT 1,
                    enabled BOOLEAN DEFAULT 1,
                    last_execution REAL,
                    next_execution REAL,
                    execution_results TEXT,
                    FOREIGN KEY (asset_id) REFERENCES data_assets (asset_id)
                )
            """)
            
            # Create disaster recovery plans table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS disaster_recovery_plans (
                    plan_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    dr_tier TEXT NOT NULL,
                    assets TEXT NOT NULL,  -- JSON array
                    rto_minutes INTEGER NOT NULL,
                    rpo_minutes INTEGER NOT NULL,
                    procedures TEXT NOT NULL,  -- JSON array
                    contacts TEXT NOT NULL,  -- JSON array
                    testing_schedule TEXT NOT NULL,
                    last_tested REAL,
                    test_results TEXT  -- JSON object
                )
            """)
            
            # Create data lineage table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_lineage (
                    lineage_id TEXT PRIMARY KEY,
                    source_asset TEXT NOT NULL,
                    target_asset TEXT NOT NULL,
                    transformation_type TEXT NOT NULL,
                    transformation_description TEXT,
                    created_date REAL NOT NULL
                )
            """)
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to initialize data governance database: {e}")
    
    def register_data_asset(
        self,
        name: str,
        data_type: str,
        classification: DataClassification,
        owner: str,
        steward: str,
        location: str,
        description: str = "",
        sensitivity_score: int = 5,
        retention_period_days: Optional[int] = None
    ) -> Optional[str]:
        """Register a new data asset."""
        try:
            asset_id = str(uuid.uuid4())
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO data_assets (
                    asset_id, name, description, data_type, classification,
                    owner, steward, location, sensitivity_score, retention_period_days,
                    created_date, last_modified, tags, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                asset_id, name, description, data_type, classification.value,
                owner, steward, location, sensitivity_score, retention_period_days,
                time.time(), time.time(), json.dumps([]), json.dumps({})
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Registered data asset: {name} ({asset_id})")
            return asset_id
            
        except Exception as e:
            logger.error(f"Failed to register data asset {name}: {e}")
            return None
    
    def update_asset_metadata(
        self,
        asset_id: str,
        size_bytes: Optional[int] = None,
        record_count: Optional[int] = None,
        last_accessed: Optional[float] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update data asset metadata."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            update_fields = []
            update_values = []
            
            if size_bytes is not None:
                update_fields.append("size_bytes = ?")
                update_values.append(size_bytes)
            
            if record_count is not None:
                update_fields.append("record_count = ?")
                update_values.append(record_count)
            
            if last_accessed is not None:
                update_fields.append("last_accessed = ?")
                update_values.append(last_accessed)
            
            if tags is not None:
                update_fields.append("tags = ?")
                update_values.append(json.dumps(tags))
            
            if metadata is not None:
                update_fields.append("metadata = ?")
                update_values.append(json.dumps(metadata))
            
            # Always update last_modified
            update_fields.append("last_modified = ?")
            update_values.append(time.time())
            
            if update_fields:
                update_values.append(asset_id)
                cursor.execute(f"""
                    UPDATE data_assets 
                    SET {', '.join(update_fields)}
                    WHERE asset_id = ?
                """, update_values)
                
                conn.commit()
                conn.close()
                
                logger.info(f"Updated metadata for asset: {asset_id}")
                return True
            else:
                conn.close()
                return False
                
        except Exception as e:
            logger.error(f"Failed to update asset metadata {asset_id}: {e}")
            return False
    
    def get_data_assets(
        self,
        classification: Optional[DataClassification] = None,
        owner: Optional[str] = None,
        data_type: Optional[str] = None
    ) -> List[DataAsset]:
        """Get data assets with optional filtering."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = "SELECT * FROM data_assets WHERE 1=1"
            params = []
            
            if classification:
                query += " AND classification = ?"
                params.append(classification.value)
            
            if owner:
                query += " AND owner = ?"
                params.append(owner)
            
            if data_type:
                query += " AND data_type = ?"
                params.append(data_type)
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()
            
            assets = []
            for row in results:
                asset = DataAsset(
                    asset_id=row[0],
                    name=row[1],
                    description=row[2],
                    data_type=row[3],
                    classification=DataClassification(row[4]),
                    owner=row[5],
                    steward=row[6],
                    location=row[7],
                    size_bytes=row[8],
                    record_count=row[9],
                    sensitivity_score=row[10],
                    retention_period_days=row[11],
                    created_date=row[12],
                    last_accessed=row[13],
                    last_modified=row[14],
                    tags=json.loads(row[15] or "[]"),
                    metadata=json.loads(row[16] or "{}")
                )
                assets.append(asset)
            
            return assets
            
        except Exception as e:
            logger.error(f"Failed to get data assets: {e}")
            return []
    
    def get_sensitive_assets(self, min_sensitivity: int = 7) -> List[DataAsset]:
        """Get assets with high sensitivity scores."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM data_assets WHERE sensitivity_score >= ?
            """, (min_sensitivity,))
            
            results = cursor.fetchall()
            conn.close()
            
            assets = []
            for row in results:
                asset = DataAsset(
                    asset_id=row[0],
                    name=row[1],
                    description=row[2],
                    data_type=row[3],
                    classification=DataClassification(row[4]),
                    owner=row[5],
                    steward=row[6],
                    location=row[7],
                    size_bytes=row[8],
                    record_count=row[9],
                    sensitivity_score=row[10],
                    retention_period_days=row[11],
                    created_date=row[12],
                    last_accessed=row[13],
                    last_modified=row[14],
                    tags=json.loads(row[15] or "[]"),
                    metadata=json.loads(row[16] or "{}")
                )
                assets.append(asset)
            
            return assets
            
        except Exception as e:
            logger.error(f"Failed to get sensitive assets: {e}")
            return []
    
    def calculate_data_volume_by_classification(self) -> Dict[str, int]:
        """Calculate total data volume by classification level."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT classification, COALESCE(SUM(size_bytes), 0) as total_size
                FROM data_assets 
                GROUP BY classification
            """)
            
            results = cursor.fetchall()
            conn.close()
            
            return {row[0]: row[1] for row in results}
            
        except Exception as e:
            logger.error(f"Failed to calculate data volume by classification: {e}")
            return {}


class DataQualityManager:
    """
    Manages data quality rules and validation.
    """
    
    def __init__(self, database_path: str = "data_governance.db"):
        self.db_path = database_path
        self.quality_metrics_cache: Dict[str, Dict[str, Any]] = {}
    
    def add_quality_rule(
        self,
        asset_id: str,
        rule_name: str,
        rule_type: str,
        rule_definition: str,
        severity: str,
        threshold: float
    ) -> Optional[str]:
        """Add a new data quality rule."""
        try:
            rule_id = str(uuid.uuid4())
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO data_quality_rules (
                    rule_id, asset_id, rule_name, rule_type, rule_definition,
                    severity, threshold, execution_results, enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rule_id, asset_id, rule_name, rule_type, rule_definition,
                severity, threshold, json.dumps({}), True
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Added quality rule: {rule_name} ({rule_id})")
            return rule_id
            
        except Exception as e:
            logger.error(f"Failed to add quality rule {rule_name}: {e}")
            return None
    
    async def execute_quality_check(self, rule_id: str) -> Dict[str, Any]:
        """Execute a data quality rule and return results."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get rule details
            cursor.execute("""
                SELECT * FROM data_quality_rules WHERE rule_id = ?
            """, (rule_id,))
            
            row = cursor.fetchone()
            if not row:
                return {"error": "Rule not found"}
            
            rule = {
                "rule_id": row[0],
                "asset_id": row[1],
                "rule_name": row[2],
                "rule_type": row[3],
                "rule_definition": row[4],
                "severity": row[5],
                "threshold": row[6],
                "last_executed": row[7],
                "execution_results": json.loads(row[8] or "{}"),
                "enabled": bool(row[9])
            }
            
            if not rule["enabled"]:
                return {"error": "Rule is disabled"}
            
            # Execute the rule (simplified implementation)
            execution_time = time.time()
            
            # This would typically execute actual SQL or validation logic
            # For now, we'll simulate rule execution
            if rule["rule_type"] == "completeness":
                result_score = 0.95  # Simulated
            elif rule["rule_type"] == "uniqueness":
                result_score = 0.98  # Simulated
            elif rule["rule_type"] == "accuracy":
                result_score = 0.92  # Simulated
            else:
                result_score = 0.90  # Default
            
            passed = result_score >= rule["threshold"]
            
            execution_result = {
                "execution_time": execution_time,
                "result_score": result_score,
                "threshold": rule["threshold"],
                "passed": passed,
                "execution_details": {
                    "rows_checked": 10000,
                    "issues_found": int((1 - result_score) * 10000),
                    "execution_duration_ms": 1500
                }
            }
            
            # Update rule with execution results
            cursor.execute("""
                UPDATE data_quality_rules 
                SET last_executed = ?, execution_results = ?
                WHERE rule_id = ?
            """, (execution_time, json.dumps(execution_result), rule_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Executed quality rule {rule['rule_name']}: {'PASSED' if passed else 'FAILED'}")
            return execution_result
            
        except Exception as e:
            logger.error(f"Failed to execute quality check for rule {rule_id}: {e}")
            return {"error": str(e)}
    
    async def run_quality_assessment(self, asset_id: str) -> Dict[str, Any]:
        """Run complete quality assessment for a data asset."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get all enabled rules for the asset
            cursor.execute("""
                SELECT rule_id, rule_name, rule_type, severity, threshold
                FROM data_quality_rules 
                WHERE asset_id = ? AND enabled = 1
            """, (asset_id,))
            
            rules = cursor.fetchall()
            conn.close()
            
            assessment_results = {
                "asset_id": asset_id,
                "assessment_time": time.time(),
                "total_rules": len(rules),
                "executed_rules": 0,
                "passed_rules": 0,
                "failed_rules": 0,
                "critical_failures": 0,
                "rule_results": [],
                "overall_quality_score": 0.0,
                "recommendations": []
            }
            
            if not rules:
                assessment_results["recommendations"].append("No quality rules configured for this asset")
                return assessment_results
            
            total_score = 0.0
            
            for rule in rules:
                result = await self.execute_quality_check(rule[0])  # rule_id
                
                if "error" not in result:
                    assessment_results["executed_rules"] += 1
                    total_score += result.get("result_score", 0.0)
                    
                    rule_result = {
                        "rule_id": rule[0],
                        "rule_name": rule[1],
                        "rule_type": rule[2],
                        "severity": rule[3],
                        "threshold": rule[4],
                        "result": result
                    }
                    
                    assessment_results["rule_results"].append(rule_result)
                    
                    if result.get("passed", False):
                        assessment_results["passed_rules"] += 1
                    else:
                        assessment_results["failed_rules"] += 1
                        if rule[3] == "critical":
                            assessment_results["critical_failures"] += 1
            
            # Calculate overall quality score
            if assessment_results["executed_rules"] > 0:
                assessment_results["overall_quality_score"] = total_score / assessment_results["executed_rules"]
            
            # Generate recommendations
            if assessment_results["critical_failures"] > 0:
                assessment_results["recommendations"].append(
                    f"Address {assessment_results['critical_failures']} critical quality issues immediately"
                )
            
            if assessment_results["overall_quality_score"] < 0.85:
                assessment_results["recommendations"].append(
                    f"Overall quality score is {assessment_results['overall_quality_score']:.2f}. Review all failed rules."
                )
            
            if assessment_results["failed_rules"] > assessment_results["passed_rules"]:
                assessment_results["recommendations"].append(
                    "More rules failed than passed. Conduct comprehensive data quality review."
                )
            
            if not assessment_results["recommendations"]:
                assessment_results["recommendations"].append("Data quality is acceptable. Continue monitoring.")
            
            return assessment_results
            
        except Exception as e:
            logger.error(f"Failed to run quality assessment for asset {asset_id}: {e}")
            return {"error": str(e)}
    
    def get_quality_trends(self, days: int = 30) -> Dict[str, Any]:
        """Get data quality trends over time."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_time = time.time() - (days * 24 * 3600)
            
            cursor.execute("""
                SELECT rule_name, rule_type, COUNT(*) as execution_count,
                       AVG(CASE WHEN json_extract(execution_results, '$.passed') = 1 THEN 1.0 ELSE 0.0 END) as pass_rate,
                       AVG(json_extract(execution_results, '$.result_score')) as avg_score
                FROM data_quality_rules 
                WHERE last_executed > ? AND enabled = 1
                GROUP BY rule_name, rule_type
                ORDER BY execution_count DESC
            """, (cutoff_time,))
            
            results = cursor.fetchall()
            conn.close()
            
            trends = {
                "period_days": days,
                "period_start": cutoff_time,
                "period_end": time.time(),
                "rule_trends": [],
                "summary": {
                    "total_executions": sum(row[2] for row in results),
                    "average_pass_rate": 0.0,
                    "most_active_rule": None,
                    "lowest_performing_rule": None
                }
            }
            
            if results:
                avg_pass_rate = sum(row[3] for row in results) / len(results)
                trends["summary"]["average_pass_rate"] = avg_pass_rate
                
                most_active = max(results, key=lambda x: x[2])
                trends["summary"]["most_active_rule"] = most_active[0]
                
                lowest_performing = min(results, key=lambda x: x[4])
                trends["summary"]["lowest_performing_rule"] = lowest_performing[0]
                
                for rule in results:
                    trends["rule_trends"].append({
                        "rule_name": rule[0],
                        "rule_type": rule[1],
                        "execution_count": rule[2],
                        "pass_rate": rule[3],
                        "average_score": rule[4]
                    })
            
            return trends
            
        except Exception as e:
            logger.error(f"Failed to get quality trends: {e}")
            return {}


class BackupManager:
    """
    Manages automated backup operations for data assets.
    """
    
    def __init__(self, database_path: str = "data_governance.db"):
        self.db_path = database_path
        self.backup_storage_path = "backups"
        self._create_backup_directory()
        self._schedule_manager = None
        self._start_scheduler()
    
    def _create_backup_directory(self) -> None:
        """Create backup storage directory."""
        try:
            os.makedirs(self.backup_storage_path, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create backup directory: {e}")
    
    def _start_scheduler(self) -> None:
        """Start the backup scheduler."""
        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        
        logger.info("Backup scheduler started")
    
    def create_backup_job(
        self,
        name: str,
        asset_id: str,
        source_location: str,
        destination_location: str,
        backup_type: BackupType,
        schedule_frequency: str,
        retention_days: int,
        compression_enabled: bool = True,
        encryption_enabled: bool = True
    ) -> Optional[str]:
        """Create a new backup job."""
        try:
            job_id = str(uuid.uuid4())
            
            # Calculate next execution time
            next_execution = self._calculate_next_execution(schedule_frequency)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO backup_jobs (
                    job_id, name, asset_id, backup_type, source_location,
                    destination_location, schedule, retention_days,
                    compression_enabled, encryption_enabled, next_execution,
                    execution_results
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id, name, asset_id, backup_type.value, source_location,
                destination_location, schedule_frequency, retention_days,
                compression_enabled, encryption_enabled, next_execution,
                json.dumps([])
            ))
            
            conn.commit()
            conn.close()
            
            # Schedule the job
            self._schedule_backup_job(job_id, schedule_frequency)
            
            logger.info(f"Created backup job: {name} ({job_id})")
            return job_id
            
        except Exception as e:
            logger.error(f"Failed to create backup job {name}: {e}")
            return None
    
    def _calculate_next_execution(self, schedule_frequency: str) -> float:
        """Calculate next execution time based on schedule."""
        now = datetime.now()
        
        if schedule_frequency == "hourly":
            next_time = now + timedelta(hours=1)
        elif schedule_frequency == "daily":
            next_time = now + timedelta(days=1)
        elif schedule_frequency == "weekly":
            next_time = now + timedelta(weeks=1)
        elif schedule_frequency == "monthly":
            next_time = now + timedelta(days=30)  # Simplified
        else:
            next_time = now + timedelta(days=1)  # Default to daily
        
        return next_time.timestamp()
    
    def _schedule_backup_job(self, job_id: str, schedule_frequency: str) -> None:
        """Schedule a backup job using the schedule library."""
        def execute_job():
            asyncio.run(self.execute_backup_job(job_id))
        
        if schedule_frequency == "hourly":
            schedule.every().hour.do(execute_job)
        elif schedule_frequency == "daily":
            schedule.every().day.at("02:00").do(execute_job)  # Run at 2 AM
        elif schedule_frequency == "weekly":
            schedule.every().sunday.at("02:00").do(execute_job)  # Run Sunday at 2 AM
        elif schedule_frequency == "monthly":
            schedule.every(30).days.at("02:00").do(execute_job)  # Run every 30 days at 2 AM
    
    async def execute_backup_job(self, job_id: str) -> Dict[str, Any]:
        """Execute a backup job."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get job details
            cursor.execute("""
                SELECT * FROM backup_jobs WHERE job_id = ?
            """, (job_id,))
            
            row = cursor.fetchone()
            if not row:
                return {"error": "Backup job not found"}
            
            job = {
                "job_id": row[0],
                "name": row[1],
                "asset_id": row[2],
                "backup_type": row[3],
                "source_location": row[4],
                "destination_location": row[5],
                "schedule": row[6],
                "retention_days": row[7],
                "compression_enabled": bool(row[8]),
                "encryption_enabled": bool(row[9]),
                "enabled": bool(row[10]),
                "last_execution": row[11],
                "next_execution": row[12],
                "execution_results": json.loads(row[13] or "[]")
            }
            
            if not job["enabled"]:
                return {"error": "Backup job is disabled"}
            
            execution_time = time.time()
            execution_id = str(uuid.uuid4())
            
            # Execute backup (simplified implementation)
            logger.info(f"Starting backup job: {job['name']}")
            
            backup_result = await self._perform_backup(job)
            
            execution_result = {
                "execution_id": execution_id,
                "execution_time": execution_time,
                "status": backup_result.get("status", "failed"),
                "source_location": job["source_location"],
                "destination_location": job["destination_location"],
                "backup_size_bytes": backup_result.get("size_bytes", 0),
                "duration_seconds": backup_result.get("duration", 0),
                "compression_ratio": backup_result.get("compression_ratio", 1.0),
                "error_message": backup_result.get("error"),
                "backup_file_path": backup_result.get("backup_path")
            }
            
            # Update job with execution results
            next_execution = self._calculate_next_execution(job["schedule"])
            
            updated_results = job["execution_results"] + [execution_result]
            # Keep only last 100 results
            updated_results = updated_results[-100:]
            
            cursor.execute("""
                UPDATE backup_jobs 
                SET last_execution = ?, next_execution = ?, execution_results = ?
                WHERE job_id = ?
            """, (execution_time, next_execution, json.dumps(updated_results), job_id))
            
            conn.commit()
            conn.close()
            
            if backup_result.get("status") == "success":
                logger.info(f"Backup job {job['name']} completed successfully")
            else:
                logger.error(f"Backup job {job['name']} failed: {backup_result.get('error')}")
            
            return execution_result
            
        except Exception as e:
            logger.error(f"Failed to execute backup job {job_id}: {e}")
            return {"error": str(e)}
    
    async def _perform_backup(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the actual backup operation."""
        try:
            start_time = time.time()
            
            source_path = job["source_location"]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{job['name']}_{timestamp}.backup"
            
            if job["backup_type"] == "full":
                backup_path = os.path.join(self.backup_storage_path, backup_filename)
            else:
                # For incremental/differential, append timestamp to existing backup
                backup_path = os.path.join(self.backup_storage_path, f"{job['name']}_incremental_{timestamp}.backup")
            
            # Simplified backup operation (would be much more sophisticated in real implementation)
            if os.path.exists(source_path):
                if job["compression_enabled"]:
                    # Create compressed backup
                    with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        if os.path.isfile(source_path):
                            zipf.write(source_path, os.path.basename(source_path))
                        else:
                            for root, dirs, files in os.walk(source_path):
                                for file in files:
                                    file_path = os.path.join(root, file)
                                    arcname = os.path.relpath(file_path, source_path)
                                    zipf.write(file_path, arcname)
                    
                    compressed_size = os.path.getsize(backup_path)
                    original_size = self._get_directory_size(source_path)
                    compression_ratio = original_size / compressed_size if compressed_size > 0 else 1.0
                    
                else:
                    # Create uncompressed backup (copy files)
                    if os.path.isfile(source_path):
                        shutil.copy2(source_path, backup_path)
                    else:
                        shutil.copytree(source_path, backup_path, dirs_exist_ok=True)
                    
                    original_size = self._get_directory_size(source_path)
                    compression_ratio = 1.0
                
                duration = time.time() - start_time
                
                return {
                    "status": "success",
                    "size_bytes": os.path.getsize(backup_path),
                    "duration": duration,
                    "compression_ratio": compression_ratio,
                    "backup_path": backup_path
                }
            else:
                return {
                    "status": "failed",
                    "error": f"Source path does not exist: {source_path}",
                    "duration": time.time() - start_time
                }
                
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "duration": time.time() - start_time
            }
    
    def _get_directory_size(self, path: str) -> int:
        """Get total size of a directory or file."""
        total_size = 0
        try:
            if os.path.isfile(path):
                return os.path.getsize(path)
            else:
                for dirpath, dirnames, filenames in os.walk(path):
                    for filename in filenames:
                        filepath = os.path.join(dirpath, filename)
                        if os.path.exists(filepath):
                            total_size += os.path.getsize(filepath)
        except Exception as e:
            logger.error(f"Failed to get directory size for {path}: {e}")
        
        return total_size
    
    def get_backup_status(self, job_id: Optional[str] = None) -> Dict[str, Any]:
        """Get backup job status and recent executions."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if job_id:
                cursor.execute("SELECT * FROM backup_jobs WHERE job_id = ?", (job_id,))
            else:
                cursor.execute("SELECT * FROM backup_jobs")
            
            jobs = cursor.fetchall()
            conn.close()
            
            if job_id and not jobs:
                return {"error": "Backup job not found"}
            
            backup_status = {
                "timestamp": time.time(),
                "total_jobs": len(jobs),
                "enabled_jobs": sum(1 for job in jobs if job[10]),  # enabled column
                "jobs": []
            }
            
            for job in jobs:
                execution_results = json.loads(job[13] or "[]")
                last_execution = execution_results[-1] if execution_results else None
                
                job_status = {
                    "job_id": job[0],
                    "name": job[1],
                    "asset_id": job[2],
                    "backup_type": job[3],
                    "schedule": job[6],
                    "enabled": job[10],
                    "last_execution": job[11],
                    "next_execution": job[12],
                    "last_execution_status": last_execution.get("status") if last_execution else "never",
                    "total_executions": len(execution_results),
                    "successful_executions": sum(1 for r in execution_results if r.get("status") == "success"),
                    "failed_executions": sum(1 for r in execution_results if r.get("status") == "failed")
                }
                
                backup_status["jobs"].append(job_status)
            
            return backup_status
            
        except Exception as e:
            logger.error(f"Failed to get backup status: {e}")
            return {"error": str(e)}


class DisasterRecoveryManager:
    """
    Manages disaster recovery plans and testing.
    """
    
    def __init__(self, database_path: str = "data_governance.db"):
        self.db_path = database_path
        self.recovery_test_results: List[Dict[str, Any]] = []
    
    def create_disaster_recovery_plan(
        self,
        name: str,
        description: str,
        dr_tier: DisasterRecoveryTier,
        assets: List[str],
        rto_minutes: int,
        rpo_minutes: int,
        procedures: List[str],
        contacts: List[str],
        testing_schedule: str
    ) -> Optional[str]:
        """Create a new disaster recovery plan."""
        try:
            plan_id = str(uuid.uuid4())
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO disaster_recovery_plans (
                    plan_id, name, description, dr_tier, assets,
                    rto_minutes, rpo_minutes, procedures, contacts,
                    testing_schedule, test_results
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plan_id, name, description, dr_tier.value, json.dumps(assets),
                rto_minutes, rpo_minutes, json.dumps(procedures), json.dumps(contacts),
                testing_schedule, json.dumps({})
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Created disaster recovery plan: {name} ({plan_id})")
            return plan_id
            
        except Exception as e:
            logger.error(f"Failed to create disaster recovery plan {name}: {e}")
            return None
    
    async def execute_recovery_test(self, plan_id: str) -> Dict[str, Any]:
        """Execute a disaster recovery test."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get plan details
            cursor.execute("""
                SELECT * FROM disaster_recovery_plans WHERE plan_id = ?
            """, (plan_id,))
            
            row = cursor.fetchone()
            if not row:
                return {"error": "Recovery plan not found"}
            
            plan = {
                "plan_id": row[0],
                "name": row[1],
                "description": row[2],
                "dr_tier": row[3],
                "assets": json.loads(row[4]),
                "rto_minutes": row[5],
                "rpo_minutes": row[6],
                "procedures": json.loads(row[7]),
                "contacts": json.loads(row[8]),
                "testing_schedule": row[9],
                "last_tested": row[10],
                "test_results": json.loads(row[11] or "{}")
            }
            
            execution_time = time.time()
            test_id = str(uuid.uuid4())
            
            logger.info(f"Starting recovery test for plan: {plan['name']}")
            
            # Simulate recovery test execution
            test_result = await self._simulate_recovery_test(plan)
            
            # Update plan with test results
            new_test_results = plan["test_results"].copy()
            new_test_results[test_id] = {
                "execution_time": execution_time,
                "test_duration": test_result.get("duration", 0),
                "success": test_result.get("success", False),
                "procedures_completed": test_result.get("procedures_completed", 0),
                "total_procedures": test_result.get("total_procedures", 0),
                "issues_found": test_result.get("issues", []),
                "recommendations": test_result.get("recommendations", [])
            }
            
            cursor.execute("""
                UPDATE disaster_recovery_plans 
                SET last_tested = ?, test_results = ?
                WHERE plan_id = ?
            """, (execution_time, json.dumps(new_test_results), plan_id))
            
            conn.commit()
            conn.close()
            
            # Store in local cache
            self.recovery_test_results.append({
                "test_id": test_id,
                "plan_id": plan_id,
                "plan_name": plan["name"],
                "execution_time": execution_time,
                "result": test_result
            })
            
            if test_result.get("success"):
                logger.info(f"Recovery test for plan {plan['name']} completed successfully")
            else:
                logger.warning(f"Recovery test for plan {plan['name']} had issues")
            
            return {
                "test_id": test_id,
                "plan_name": plan["name"],
                "execution_time": execution_time,
                "test_result": test_result
            }
            
        except Exception as e:
            logger.error(f"Failed to execute recovery test for plan {plan_id}: {e}")
            return {"error": str(e)}
    
    async def _simulate_recovery_test(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate a disaster recovery test (simplified)."""
        start_time = time.time()
        
        try:
            total_procedures = len(plan["procedures"])
            completed_procedures = 0
            issues = []
            
            # Simulate procedure execution
            for i, procedure in enumerate(plan["procedures"]):
                # Simulate procedure execution time
                await asyncio.sleep(0.1)  # Short delay
                
                # Simulate random failures for some procedures
                import random
                if random.random() < 0.1:  # 10% chance of issue
                    issues.append(f"Procedure {i+1} had minor issues: {procedure}")
                else:
                    completed_procedures += 1
            
            duration = time.time() - start_time
            success = completed_procedures >= total_procedures * 0.8  # 80% success rate required
            
            recommendations = []
            if issues:
                recommendations.append("Review and fix identified issues in recovery procedures")
            if duration > plan["rto_minutes"] * 60:  # Convert minutes to seconds
                recommendations.append(f"Test took {duration/60:.1f} minutes, exceeds RTO of {plan['rto_minutes']} minutes")
            
            if not recommendations:
                recommendations.append("Recovery test passed successfully. Continue regular testing.")
            
            return {
                "success": success,
                "duration": duration,
                "procedures_completed": completed_procedures,
                "total_procedures": total_procedures,
                "issues": issues,
                "recommendations": recommendations
            }
            
        except Exception as e:
            return {
                "success": False,
                "duration": time.time() - start_time,
                "procedures_completed": 0,
                "total_procedures": len(plan["procedures"]),
                "issues": [f"Test execution failed: {str(e)}"],
                "recommendations": ["Fix test execution issues and rerun test"]
            }
    
    def get_disaster_recovery_status(self) -> Dict[str, Any]:
        """Get disaster recovery status for all plans."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM disaster_recovery_plans")
            plans = cursor.fetchall()
            conn.close()
            
            dr_status = {
                "timestamp": time.time(),
                "total_plans": len(plans),
                "plans": []
            }
            
            for plan in plans:
                test_results = json.loads(plan[11] or "{}")
                last_test = None
                if test_results:
                    latest_test_id = max(test_results.keys())
                    last_test = test_results[latest_test_id]
                
                plan_status = {
                    "plan_id": plan[0],
                    "name": plan[1],
                    "description": plan[2],
                    "dr_tier": plan[3],
                    "rto_minutes": plan[5],
                    "rpo_minutes": plan[6],
                    "testing_schedule": plan[9],
                    "last_tested": plan[10],
                    "assets_count": len(json.loads(plan[4])),
                    "procedures_count": len(json.loads(plan[7])),
                    "contacts_count": len(json.loads(plan[8])),
                    "has_recent_test": False,
                    "test_success_rate": 0.0,
                    "last_test_status": "never_tested"
                }
                
                if last_test:
                    plan_status["has_recent_test"] = (time.time() - last_test["execution_time"]) < (30 * 24 * 3600)  # 30 days
                    plan_status["test_success_rate"] = sum(1 for result in test_results.values() if result.get("success", False)) / len(test_results) * 100
                    plan_status["last_test_status"] = "success" if last_test.get("success", False) else "failed"
                
                dr_status["plans"].append(plan_status)
            
            return dr_status
            
        except Exception as e:
            logger.error(f"Failed to get disaster recovery status: {e}")
            return {"error": str(e)}
    
    def get_overdue_tests(self, max_age_days: int = 90) -> List[Dict[str, Any]]:
        """Get disaster recovery plans with overdue tests."""
        try:
            cutoff_time = time.time() - (max_age_days * 24 * 3600)
            dr_status = self.get_disaster_recovery_status()
            
            overdue_plans = []
            for plan in dr_status.get("plans", []):
                last_tested = plan.get("last_tested")
                if not last_tested or last_tested < cutoff_time:
                    overdue_plans.append({
                        "plan_id": plan["plan_id"],
                        "plan_name": plan["name"],
                        "dr_tier": plan["dr_tier"],
                        "last_tested": last_tested,
                        "days_since_test": (time.time() - last_tested) / (24 * 3600) if last_tested else float('inf'),
                        "testing_schedule": plan["testing_schedule"]
                    })
            
            return overdue_plans
            
        except Exception as e:
            logger.error(f"Failed to get overdue tests: {e}")
            return []


class EnterpriseDataGovernanceOrchestrator:
    """
    Main orchestrator for enterprise data governance.
    Integrates all data management components.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Initialize components
        self.asset_manager = DataAssetManager(
            self.config.get('database_path', 'data_governance.db')
        )
        self.quality_manager = DataQualityManager(
            self.config.get('database_path', 'data_governance.db')
        )
        self.backup_manager = BackupManager(
            self.config.get('database_path', 'data_governance.db')
        )
        self.dr_manager = DisasterRecoveryManager(
            self.config.get('database_path', 'data_governance.db')
        )
        
        # Initialize default data assets and rules
        self._initialize_default_data_governance()
        
        self.running = False
        self.governance_task = None
    
    def _initialize_default_data_governance(self) -> None:
        """Initialize default data governance framework."""
        
        # Register default data assets
        default_assets = [
            {
                "name": "User Authentication Database",
                "data_type": "database",
                "classification": DataClassification.CONFIDENTIAL,
                "owner": "IT Security",
                "steward": "Database Administrator",
                "location": "auth_db",
                "sensitivity_score": 9,
                "description": "Contains user credentials and authentication data"
            },
            {
                "name": "Application Logs",
                "data_type": "file_system",
                "classification": DataClassification.INTERNAL,
                "owner": "Operations",
                "steward": "DevOps Team",
                "location": "/var/log/app",
                "sensitivity_score": 3,
                "description": "Application and system logs"
            },
            {
                "name": "Customer Data Warehouse",
                "data_type": "database",
                "classification": DataClassification.RESTRICTED,
                "owner": "Data Analytics",
                "steward": "Data Steward",
                "location": "analytics_db",
                "sensitivity_score": 10,
                "description": "Aggregated customer analytics and reporting data"
            }
        ]
        
        for asset_config in default_assets:
            self.asset_manager.register_data_asset(**asset_config)
        
        # Add default data quality rules
        assets = self.asset_manager.get_data_assets()
        for asset in assets:
            if asset.data_type == "database":
                self.quality_manager.add_quality_rule(
                    asset_id=asset.asset_id,
                    rule_name=f"Completeness Check - {asset.name}",
                    rule_type="completeness",
                    rule_definition="SELECT COUNT(*) / (SELECT COUNT(*) FROM table) * 100 FROM table WHERE column IS NOT NULL",
                    severity="high",
                    threshold=0.95
                )
                
                self.quality_manager.add_quality_rule(
                    asset_id=asset.asset_id,
                    rule_name=f"Uniqueness Check - {asset.name}",
                    rule_type="uniqueness",
                    rule_definition="SELECT DISTINCT_COUNT / TOTAL_COUNT * 100 FROM table",
                    severity="medium",
                    threshold=0.98
                )
        
        # Create default backup jobs
        for asset in assets:
            if asset.classification in [DataClassification.CONFIDENTIAL, DataClassification.RESTRICTED]:
                self.backup_manager.create_backup_job(
                    name=f"Daily Backup - {asset.name}",
                    asset_id=asset.asset_id,
                    source_location=asset.location,
                    destination_location=f"backups/{asset.name}",
                    backup_type=BackupType.FULL,
                    schedule_frequency="daily",
                    retention_days=30,
                    compression_enabled=True,
                    encryption_enabled=True
                )
        
        # Create default disaster recovery plan
        sensitive_assets = self.asset_manager.get_sensitive_assets(min_sensitivity=8)
        if sensitive_assets:
            asset_ids = [asset.asset_id for asset in sensitive_assets]
            
            self.dr_manager.create_disaster_recovery_plan(
                name="Primary Database Disaster Recovery",
                description="Recovery plan for critical database assets",
                dr_tier=DisasterRecoveryTier.TIER_1,
                assets=asset_ids,
                rto_minutes=60,
                rpo_minutes=15,
                procedures=[
                    "Verify database server failure",
                    "Activate standby database server",
                    "Update DNS records to point to standby",
                    "Verify application connectivity",
                    "Run health checks on all services"
                ],
                contacts=["IT Security Manager", "Database Administrator", "Operations Lead"],
                testing_schedule="monthly"
            )
    
    async def run_data_governance_assessment(self) -> Dict[str, Any]:
        """Run comprehensive data governance assessment."""
        assessment_results = {
            "timestamp": time.time(),
            "data_assets": {},
            "data_quality": {},
            "backup_status": {},
            "disaster_recovery": {},
            "overall_score": 0.0,
            "critical_issues": [],
            "recommendations": []
        }
        
        # Assess data assets
        assets = self.asset_manager.get_data_assets()
        sensitive_assets = self.asset_manager.get_sensitive_assets()
        classification_volume = self.asset_manager.calculate_data_volume_by_classification()
        
        assessment_results["data_assets"] = {
            "total_assets": len(assets),
            "sensitive_assets": len(sensitive_assets),
            "classification_distribution": classification_volume,
            "high_risk_assets": len([a for a in assets if a.sensitivity_score >= 8])
        }
        
        # Assess data quality
        quality_trends = self.quality_manager.get_quality_trends()
        assessment_results["data_quality"] = quality_trends
        
        # Assess backup status
        backup_status = self.backup_manager.get_backup_status()
        assessment_results["backup_status"] = backup_status
        
        # Assess disaster recovery
        dr_status = self.dr_manager.get_disaster_recovery_status()
        overdue_tests = self.dr_manager.get_overdue_tests()
        
        assessment_results["disaster_recovery"] = {
            **dr_status,
            "overdue_tests": len(overdue_tests),
            "overdue_test_details": overdue_tests
        }
        
        # Calculate overall governance score
        scores = []
        
        # Asset classification score
        total_assets = len(assets)
        classified_assets = len([a for a in assets if a.classification != DataClassification.PUBLIC])
        asset_score = (classified_assets / total_assets * 100) if total_assets > 0 else 100
        scores.append(asset_score)
        
        # Data quality score
        quality_score = quality_trends.get("summary", {}).get("average_pass_rate", 0.0) * 100
        scores.append(quality_score)
        
        # Backup coverage score
        backup_coverage = (backup_status.get("enabled_jobs", 0) / max(backup_status.get("total_jobs", 1), 1)) * 100
        scores.append(backup_coverage)
        
        # Disaster recovery score
        dr_score = 100 - (len(overdue_tests) * 20)  # Deduct 20 points per overdue test
        scores.append(max(dr_score, 0))
        
        assessment_results["overall_score"] = sum(scores) / len(scores) if scores else 0
        
        # Identify critical issues
        if len([a for a in sensitive_assets if a.sensitivity_score >= 9]) > 0:
            assessment_results["critical_issues"].append("High-sensitivity assets without adequate protection")
        
        if quality_trends.get("summary", {}).get("average_pass_rate", 1.0) < 0.8:
            assessment_results["critical_issues"].append("Poor data quality across multiple assets")
        
        if backup_status.get("failed_executions", 0) > backup_status.get("successful_executions", 1):
            assessment_results["critical_issues"].append("Backup failure rate exceeds success rate")
        
        if len(overdue_tests) > 0:
            assessment_results["critical_issues"].append(f"{len(overdue_tests)} disaster recovery tests are overdue")
        
        # Generate recommendations
        recommendations = []
        
        if assessment_results["overall_score"] < 70:
            recommendations.append("Overall data governance score is below acceptable threshold. Comprehensive review needed.")
        
        for issue in assessment_results["critical_issues"]:
            if "high-sensitivity" in issue:
                recommendations.append("Implement additional security controls for high-sensitivity data assets")
            elif "data quality" in issue:
                recommendations.append("Review and fix data quality issues to improve reliability")
            elif "backup" in issue:
                recommendations.append("Investigate and resolve backup failures immediately")
            elif "disaster recovery" in issue:
                recommendations.append("Schedule overdue disaster recovery tests immediately")
        
        if not recommendations:
            recommendations.append("Data governance posture is good. Continue monitoring and regular assessments.")
        
        assessment_results["recommendations"] = recommendations
        
        return assessment_results
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get data governance system health information."""
        health = {
            "timestamp": time.time(),
            "governance_status": "active",
            "data_assets": {},
            "quality_metrics": {},
            "backup_health": {},
            "dr_health": {},
            "overall_healthy": True
        }
        
        try:
            # Data asset health
            assets = self.asset_manager.get_data_assets()
            sensitive_assets = self.asset_manager.get_sensitive_assets()
            
            health["data_assets"] = {
                "total": len(assets),
                "sensitive": len(sensitive_assets),
                "unclassified": len([a for a in assets if a.classification == DataClassification.PUBLIC])
            }
            
            # Quality metrics
            quality_trends = self.quality_manager.get_quality_trends()
            health["quality_metrics"] = {
                "average_pass_rate": quality_trends.get("summary", {}).get("average_pass_rate", 0.0),
                "total_executions": quality_trends.get("summary", {}).get("total_executions", 0)
            }
            
            # Backup health
            backup_status = self.backup_manager.get_backup_status()
            health["backup_health"] = {
                "total_jobs": backup_status.get("total_jobs", 0),
                "enabled_jobs": backup_status.get("enabled_jobs", 0),
                "success_rate": (
                    backup_status.get("jobs", [{}])[0].get("successful_executions", 0) /
                    max(backup_status.get("jobs", [{}])[0].get("total_executions", 1), 1) * 100
                    if backup_status.get("jobs") else 0
                )
            }
            
            # DR health
            dr_status = self.dr_manager.get_disaster_recovery_status()
            overdue_tests = self.dr_manager.get_overdue_tests()
            
            health["dr_health"] = {
                "total_plans": dr_status.get("total_plans", 0),
                "overdue_tests": len(overdue_tests),
                "last_test_age_days": min([
                    (time.time() - plan.get("last_tested", time.time())) / (24 * 3600)
                    for plan in dr_status.get("plans", []) if plan.get("last_tested")
                ]) if dr_status.get("plans") else float('inf')
            }
            
            # Overall health assessment
            issues = []
            if health["quality_metrics"]["average_pass_rate"] < 0.8:
                issues.append("Low data quality pass rate")
            if health["backup_health"]["success_rate"] < 80:
                issues.append("Poor backup success rate")
            if health["dr_health"]["overdue_tests"] > 0:
                issues.append("Overdue disaster recovery tests")
            
            health["overall_healthy"] = len(issues) == 0
            health["identified_issues"] = issues
            
        except Exception as e:
            logger.error(f"Failed to get data governance health: {e}")
            health["error"] = str(e)
            health["overall_healthy"] = False
        
        return health
    
    async def start_data_governance_monitoring(self) -> None:
        """Start data governance monitoring background tasks."""
        if self.running:
            logger.warning("Data governance monitoring already running")
            return
        
        self.running = True
        
        # Start background governance monitoring
        self.governance_task = asyncio.create_task(self._governance_monitoring_loop())
        
        logger.info("Enterprise data governance monitoring started")
    
    async def stop_data_governance_monitoring(self) -> None:
        """Stop data governance monitoring."""
        self.running = False
        
        if self.governance_task:
            self.governance_task.cancel()
            try:
                await self.governance_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Enterprise data governance monitoring stopped")
    
    async def _governance_monitoring_loop(self) -> None:
        """Background task for data governance monitoring."""
        while self.running:
            try:
                # Run periodic assessments (daily)
                assessment_results = await self.run_data_governance_assessment()
                
                if assessment_results["overall_score"] < 70:
                    logger.warning(f"Data governance score below threshold: {assessment_results['overall_score']:.1f}%")
                
                if assessment_results["critical_issues"]:
                    logger.warning(f"Found {len(assessment_results['critical_issues'])} critical data governance issues")
                
                # Check for backup failures
                backup_status = self.backup_manager.get_backup_status()
                for job in backup_status.get("jobs", []):
                    if job.get("failed_executions", 0) > job.get("successful_executions", 0):
                        logger.warning(f"Backup job {job['name']} has more failures than successes")
                
                # Check for overdue DR tests
                overdue_tests = self.dr_manager.get_overdue_tests()
                if overdue_tests:
                    logger.warning(f"Found {len(overdue_tests)} overdue disaster recovery tests")
                
                await asyncio.sleep(3600)  # Check every hour
                
            except Exception as e:
                logger.error(f"Error in data governance monitoring: {e}")
                await asyncio.sleep(3600)


# Global data governance orchestrator instance
enterprise_data_governance: Optional[EnterpriseDataGovernanceOrchestrator] = None


async def get_enterprise_data_governance(config: Optional[Dict[str, Any]] = None) -> EnterpriseDataGovernanceOrchestrator:
    """Get or create enterprise data governance orchestrator instance."""
    global enterprise_data_governance
    
    if enterprise_data_governance is None:
        enterprise_data_governance = EnterpriseDataGovernanceOrchestrator(config)
        await enterprise_data_governance.start_data_governance_monitoring()
    
    return enterprise_data_governanceEnterprise Data Management and Governance System
Implements data lifecycle management, automated backup/disaster recovery,
data classification, and quality monitoring for enterprise-grade data governance.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import hashlib
import shutil
import os
import sqlite3
import csv
import zipfile
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Set, Union
from enum import Enum
from datetime import datetime, timedelta
import uuid
import schedule
import threading
import pickle
from pathlib import Path

# Database and storage libraries
try:
    import boto3
    import psycopg2
    import redis
    from sqlalchemy import create_engine, text
    STORAGE_AVAILABLE = True
except ImportError:
    STORAGE_AVAILABLE = False

logger = logging.getLogger(__name__)


class DataClassification(Enum):
    """Data classification levels."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_SECRET = "top_secret"


class DataQuality(Enum):
    """Data quality levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


class BackupType(Enum):
    """Types of backup operations."""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    SNAPSHOT = "snapshot"


class DisasterRecoveryTier(Enum):
    """Disaster recovery tiers with RTO/RPO objectives."""
    TIER_0 = "tier_0"  # RTO: <1 min, RPO: <1 min
    TIER_1 = "tier_1"  # RTO: <1 hour, RPO: <1 hour
    TIER_2 = "tier_2"  # RTO: <4 hours, RPO: <24 hours
    TIER_3 = "tier_3"  # RTO: <24 hours, RPO: <1 week
    TIER_4 = "tier_4"  # RTO: <1 week, RPO: <1 month


@dataclass
class DataAsset:
    """Individual data asset definition."""
    asset_id: str
    name: str
    description: str
    data_type: str  # "database", "file_system", "cloud_storage", "application_data"
    classification: DataClassification
    owner: str
    steward: str
    location: str  # "database_name", "file_path", "bucket_name"
    size_bytes: Optional[int] = None
    record_count: Optional[int] = None
    sensitivity_score: int = 0  # 1-10 scale
    retention_period_days: Optional[int] = None
    created_date: float = field(default_factory=time.time)
    last_accessed: Optional[float] = None
    last_modified: Optional[float] = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataQualityRule:
    """Data quality validation rule."""
    rule_id: str
    asset_id: str
    rule_name: str
    rule_type: str  # "completeness", "uniqueness", "accuracy", "validity", "consistency"
    rule_definition: str  # SQL query or validation logic
    severity: str  # "critical", "high", "medium", "low"
    threshold: float  # Expected percentage (e.g., 0.95 for 95%)
    last_executed: Optional[float] = None
    execution_results: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class BackupJob:
    """Backup job definition."""
    job_id: str
    name: str
    asset_id: str
    backup_type: BackupType
    source_location: str
    destination_location: str
    schedule: str  # "daily", "weekly", "monthly", "hourly"
    retention_days: int
    compression_enabled: bool = True
    encryption_enabled: bool = True
    enabled: bool = True
    last_execution: Optional[float] = None
    next_execution: Optional[float] = None
    execution_results: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DisasterRecoveryPlan:
    """Disaster recovery plan definition."""
    plan_id: str
    name: str
    description: str
    dr_tier: DisasterRecoveryTier
    assets: List[str]  # List of asset_ids
    rto_minutes: int  # Recovery Time Objective
    rpo_minutes: int  # Recovery Point Objective
    procedures: List[str]  # Step-by-step procedures
    contacts: List[str]  # Emergency contacts
    testing_schedule: str  # "monthly", "quarterly", "annually"
    last_tested: Optional[float] = None
    test_results: Dict[str, Any] = field(default_factory=dict)


class DataAssetManager:
    """
    Manages enterprise data assets, classification, and metadata.
    """
    
    def __init__(self, database_path: str = "data_governance.db"):
        self.db_path = database_path
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize data governance database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create data assets table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_assets (
                    asset_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    data_type TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    steward TEXT NOT NULL,
                    location TEXT NOT NULL,
                    size_bytes INTEGER,
                    record_count INTEGER,
                    sensitivity_score INTEGER,
                    retention_period_days INTEGER,
                    created_date REAL,
                    last_accessed REAL,
                    last_modified REAL,
                    tags TEXT,
                    metadata TEXT
                )
            """)
            
            # Create data quality rules table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_quality_rules (
                    rule_id TEXT PRIMARY KEY,
                    asset_id TEXT NOT NULL,
                    rule_name TEXT NOT NULL,
                    rule_type TEXT NOT NULL,
                    rule_definition TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    threshold REAL NOT NULL,
                    last_executed REAL,
                    execution_results TEXT,
                    enabled BOOLEAN DEFAULT 1,
                    FOREIGN KEY (asset_id) REFERENCES data_assets (asset_id)
                )
            """)
            
            # Create backup jobs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backup_jobs (
                    job_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    backup_type TEXT NOT NULL,
                    source_location TEXT NOT NULL,
                    destination_location TEXT NOT NULL,
                    schedule TEXT NOT NULL,
                    retention_days INTEGER NOT NULL,
                    compression_enabled BOOLEAN DEFAULT 1,
                    encryption_enabled BOOLEAN DEFAULT 1,
                    enabled BOOLEAN DEFAULT 1,
                    last_execution REAL,
                    next_execution REAL,
                    execution_results TEXT,
                    FOREIGN KEY (asset_id) REFERENCES data_assets (asset_id)
                )
            """)
            
            # Create disaster recovery plans table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS disaster_recovery_plans (
                    plan_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    dr_tier TEXT NOT NULL,
                    assets TEXT NOT NULL,  -- JSON array
                    rto_minutes INTEGER NOT NULL,
                    rpo_minutes INTEGER NOT NULL,
                    procedures TEXT NOT NULL,  -- JSON array
                    contacts TEXT NOT NULL,  -- JSON array
                    testing_schedule TEXT NOT NULL,
                    last_tested REAL,
                    test_results TEXT  -- JSON object
                )
            """)
            
            # Create data lineage table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_lineage (
                    lineage_id TEXT PRIMARY KEY,
                    source_asset TEXT NOT NULL,
                    target_asset TEXT NOT NULL,
                    transformation_type TEXT NOT NULL,
                    transformation_description TEXT,
                    created_date REAL NOT NULL
                )
            """)
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to initialize data governance database: {e}")
    
    def register_data_asset(
        self,
        name: str,
        data_type: str,
        classification: DataClassification,
        owner: str,
        steward: str,
        location: str,
        description: str = "",
        sensitivity_score: int = 5,
        retention_period_days: Optional[int] = None
    ) -> Optional[str]:
        """Register a new data asset."""
        try:
            asset_id = str(uuid.uuid4())
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO data_assets (
                    asset_id, name, description, data_type, classification,
                    owner, steward, location, sensitivity_score, retention_period_days,
                    created_date, last_modified, tags, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                asset_id, name, description, data_type, classification.value,
                owner, steward, location, sensitivity_score, retention_period_days,
                time.time(), time.time(), json.dumps([]), json.dumps({})
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Registered data asset: {name} ({asset_id})")
            return asset_id
            
        except Exception as e:
            logger.error(f"Failed to register data asset {name}: {e}")
            return None
    
    def update_asset_metadata(
        self,
        asset_id: str,
        size_bytes: Optional[int] = None,
        record_count: Optional[int] = None,
        last_accessed: Optional[float] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update data asset metadata."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            update_fields = []
            update_values = []
            
            if size_bytes is not None:
                update_fields.append("size_bytes = ?")
                update_values.append(size_bytes)
            
            if record_count is not None:
                update_fields.append("record_count = ?")
                update_values.append(record_count)
            
            if last_accessed is not None:
                update_fields.append("last_accessed = ?")
                update_values.append(last_accessed)
            
            if tags is not None:
                update_fields.append("tags = ?")
                update_values.append(json.dumps(tags))
            
            if metadata is not None:
                update_fields.append("metadata = ?")
                update_values.append(json.dumps(metadata))
            
            # Always update last_modified
            update_fields.append("last_modified = ?")
            update_values.append(time.time())
            
            if update_fields:
                update_values.append(asset_id)
                cursor.execute(f"""
                    UPDATE data_assets 
                    SET {', '.join(update_fields)}
                    WHERE asset_id = ?
                """, update_values)
                
                conn.commit()
                conn.close()
                
                logger.info(f"Updated metadata for asset: {asset_id}")
                return True
            else:
                conn.close()
                return False
                
        except Exception as e:
            logger.error(f"Failed to update asset metadata {asset_id}: {e}")
            return False
    
    def get_data_assets(
        self,
        classification: Optional[DataClassification] = None,
        owner: Optional[str] = None,
        data_type: Optional[str] = None
    ) -> List[DataAsset]:
        """Get data assets with optional filtering."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = "SELECT * FROM data_assets WHERE 1=1"
            params = []
            
            if classification:
                query += " AND classification = ?"
                params.append(classification.value)
            
            if owner:
                query += " AND owner = ?"
                params.append(owner)
            
            if data_type:
                query += " AND data_type = ?"
                params.append(data_type)
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()
            
            assets = []
            for row in results:
                asset = DataAsset(
                    asset_id=row[0],
                    name=row[1],
                    description=row[2],
                    data_type=row[3],
                    classification=DataClassification(row[4]),
                    owner=row[5],
                    steward=row[6],
                    location=row[7],
                    size_bytes=row[8],
                    record_count=row[9],
                    sensitivity_score=row[10],
                    retention_period_days=row[11],
                    created_date=row[12],
                    last_accessed=row[13],
                    last_modified=row[14],
                    tags=json.loads(row[15] or "[]"),
                    metadata=json.loads(row[16] or "{}")
                )
                assets.append(asset)
            
            return assets
            
        except Exception as e:
            logger.error(f"Failed to get data assets: {e}")
            return []
    
    def get_sensitive_assets(self, min_sensitivity: int = 7) -> List[DataAsset]:
        """Get assets with high sensitivity scores."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM data_assets WHERE sensitivity_score >= ?
            """, (min_sensitivity,))
            
            results = cursor.fetchall()
            conn.close()
            
            assets = []
            for row in results:
                asset = DataAsset(
                    asset_id=row[0],
                    name=row[1],
                    description=row[2],
                    data_type=row[3],
                    classification=DataClassification(row[4]),
                    owner=row[5],
                    steward=row[6],
                    location=row[7],
                    size_bytes=row[8],
                    record_count=row[9],
                    sensitivity_score=row[10],
                    retention_period_days=row[11],
                    created_date=row[12],
                    last_accessed=row[13],
                    last_modified=row[14],
                    tags=json.loads(row[15] or "[]"),
                    metadata=json.loads(row[16] or "{}")
                )
                assets.append(asset)
            
            return assets
            
        except Exception as e:
            logger.error(f"Failed to get sensitive assets: {e}")
            return []
    
    def calculate_data_volume_by_classification(self) -> Dict[str, int]:
        """Calculate total data volume by classification level."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT classification, COALESCE(SUM(size_bytes), 0) as total_size
                FROM data_assets 
                GROUP BY classification
            """)
            
            results = cursor.fetchall()
            conn.close()
            
            return {row[0]: row[1] for row in results}
            
        except Exception as e:
            logger.error(f"Failed to calculate data volume by classification: {e}")
            return {}


class DataQualityManager:
    """
    Manages data quality rules and validation.
    """
    
    def __init__(self, database_path: str = "data_governance.db"):
        self.db_path = database_path
        self.quality_metrics_cache: Dict[str, Dict[str, Any]] = {}
    
    def add_quality_rule(
        self,
        asset_id: str,
        rule_name: str,
        rule_type: str,
        rule_definition: str,
        severity: str,
        threshold: float
    ) -> Optional[str]:
        """Add a new data quality rule."""
        try:
            rule_id = str(uuid.uuid4())
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO data_quality_rules (
                    rule_id, asset_id, rule_name, rule_type, rule_definition,
                    severity, threshold, execution_results, enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rule_id, asset_id, rule_name, rule_type, rule_definition,
                severity, threshold, json.dumps({}), True
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Added quality rule: {rule_name} ({rule_id})")
            return rule_id
            
        except Exception as e:
            logger.error(f"Failed to add quality rule {rule_name}: {e}")
            return None
    
    async def execute_quality_check(self, rule_id: str) -> Dict[str, Any]:
        """Execute a data quality rule and return results."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get rule details
            cursor.execute("""
                SELECT * FROM data_quality_rules WHERE rule_id = ?
            """, (rule_id,))
            
            row = cursor.fetchone()
            if not row:
                return {"error": "Rule not found"}
            
            rule = {
                "rule_id": row[0],
                "asset_id": row[1],
                "rule_name": row[2],
                "rule_type": row[3],
                "rule_definition": row[4],
                "severity": row[5],
                "threshold": row[6],
                "last_executed": row[7],
                "execution_results": json.loads(row[8] or "{}"),
                "enabled": bool(row[9])
            }
            
            if not rule["enabled"]:
                return {"error": "Rule is disabled"}
            
            # Execute the rule (simplified implementation)
            execution_time = time.time()
            
            # This would typically execute actual SQL or validation logic
            # For now, we'll simulate rule execution
            if rule["rule_type"] == "completeness":
                result_score = 0.95  # Simulated
            elif rule["rule_type"] == "uniqueness":
                result_score = 0.98  # Simulated
            elif rule["rule_type"] == "accuracy":
                result_score = 0.92  # Simulated
            else:
                result_score = 0.90  # Default
            
            passed = result_score >= rule["threshold"]
            
            execution_result = {
                "execution_time": execution_time,
                "result_score": result_score,
                "threshold": rule["threshold"],
                "passed": passed,
                "execution_details": {
                    "rows_checked": 10000,
                    "issues_found": int((1 - result_score) * 10000),
                    "execution_duration_ms": 1500
                }
            }
            
            # Update rule with execution results
            cursor.execute("""
                UPDATE data_quality_rules 
                SET last_executed = ?, execution_results = ?
                WHERE rule_id = ?
            """, (execution_time, json.dumps(execution_result), rule_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Executed quality rule {rule['rule_name']}: {'PASSED' if passed else 'FAILED'}")
            return execution_result
            
        except Exception as e:
            logger.error(f"Failed to execute quality check for rule {rule_id}: {e}")
            return {"error": str(e)}
    
    async def run_quality_assessment(self, asset_id: str) -> Dict[str, Any]:
        """Run complete quality assessment for a data asset."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get all enabled rules for the asset
            cursor.execute("""
                SELECT rule_id, rule_name, rule_type, severity, threshold
                FROM data_quality_rules 
                WHERE asset_id = ? AND enabled = 1
            """, (asset_id,))
            
            rules = cursor.fetchall()
            conn.close()
            
            assessment_results = {
                "asset_id": asset_id,
                "assessment_time": time.time(),
                "total_rules": len(rules),
                "executed_rules": 0,
                "passed_rules": 0,
                "failed_rules": 0,
                "critical_failures": 0,
                "rule_results": [],
                "overall_quality_score": 0.0,
                "recommendations": []
            }
            
            if not rules:
                assessment_results["recommendations"].append("No quality rules configured for this asset")
                return assessment_results
            
            total_score = 0.0
            
            for rule in rules:
                result = await self.execute_quality_check(rule[0])  # rule_id
                
                if "error" not in result:
                    assessment_results["executed_rules"] += 1
                    total_score += result.get("result_score", 0.0)
                    
                    rule_result = {
                        "rule_id": rule[0],
                        "rule_name": rule[1],
                        "rule_type": rule[2],
                        "severity": rule[3],
                        "threshold": rule[4],
                        "result": result
                    }
                    
                    assessment_results["rule_results"].append(rule_result)
                    
                    if result.get("passed", False):
                        assessment_results["passed_rules"] += 1
                    else:
                        assessment_results["failed_rules"] += 1
                        if rule[3] == "critical":
                            assessment_results["critical_failures"] += 1
            
            # Calculate overall quality score
            if assessment_results["executed_rules"] > 0:
                assessment_results["overall_quality_score"] = total_score / assessment_results["executed_rules"]
            
            # Generate recommendations
            if assessment_results["critical_failures"] > 0:
                assessment_results["recommendations"].append(
                    f"Address {assessment_results['critical_failures']} critical quality issues immediately"
                )
            
            if assessment_results["overall_quality_score"] < 0.85:
                assessment_results["recommendations"].append(
                    f"Overall quality score is {assessment_results['overall_quality_score']:.2f}. Review all failed rules."
                )
            
            if assessment_results["failed_rules"] > assessment_results["passed_rules"]:
                assessment_results["recommendations"].append(
                    "More rules failed than passed. Conduct comprehensive data quality review."
                )
            
            if not assessment_results["recommendations"]:
                assessment_results["recommendations"].append("Data quality is acceptable. Continue monitoring.")
            
            return assessment_results
            
        except Exception as e:
            logger.error(f"Failed to run quality assessment for asset {asset_id}: {e}")
            return {"error": str(e)}
    
    def get_quality_trends(self, days: int = 30) -> Dict[str, Any]:
        """Get data quality trends over time."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_time = time.time() - (days * 24 * 3600)
            
            cursor.execute("""
                SELECT rule_name, rule_type, COUNT(*) as execution_count,
                       AVG(CASE WHEN json_extract(execution_results, '$.passed') = 1 THEN 1.0 ELSE 0.0 END) as pass_rate,
                       AVG(json_extract(execution_results, '$.result_score')) as avg_score
                FROM data_quality_rules 
                WHERE last_executed > ? AND enabled = 1
                GROUP BY rule_name, rule_type
                ORDER BY execution_count DESC
            """, (cutoff_time,))
            
            results = cursor.fetchall()
            conn.close()
            
            trends = {
                "period_days": days,
                "period_start": cutoff_time,
                "period_end": time.time(),
                "rule_trends": [],
                "summary": {
                    "total_executions": sum(row[2] for row in results),
                    "average_pass_rate": 0.0,
                    "most_active_rule": None,
                    "lowest_performing_rule": None
                }
            }
            
            if results:
                avg_pass_rate = sum(row[3] for row in results) / len(results)
                trends["summary"]["average_pass_rate"] = avg_pass_rate
                
                most_active = max(results, key=lambda x: x[2])
                trends["summary"]["most_active_rule"] = most_active[0]
                
                lowest_performing = min(results, key=lambda x: x[4])
                trends["summary"]["lowest_performing_rule"] = lowest_performing[0]
                
                for rule in results:
                    trends["rule_trends"].append({
                        "rule_name": rule[0],
                        "rule_type": rule[1],
                        "execution_count": rule[2],
                        "pass_rate": rule[3],
                        "average_score": rule[4]
                    })
            
            return trends
            
        except Exception as e:
            logger.error(f"Failed to get quality trends: {e}")
            return {}


class BackupManager:
    """
    Manages automated backup operations for data assets.
    """
    
    def __init__(self, database_path: str = "data_governance.db"):
        self.db_path = database_path
        self.backup_storage_path = "backups"
        self._create_backup_directory()
        self._schedule_manager = None
        self._start_scheduler()
    
    def _create_backup_directory(self) -> None:
        """Create backup storage directory."""
        try:
            os.makedirs(self.backup_storage_path, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create backup directory: {e}")
    
    def _start_scheduler(self) -> None:
        """Start the backup scheduler."""
        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        
        logger.info("Backup scheduler started")
    
    def create_backup_job(
        self,
        name: str,
        asset_id: str,
        source_location: str,
        destination_location: str,
        backup_type: BackupType,
        schedule_frequency: str,
        retention_days: int,
        compression_enabled: bool = True,
        encryption_enabled: bool = True
    ) -> Optional[str]:
        """Create a new backup job."""
        try:
            job_id = str(uuid.uuid4())
            
            # Calculate next execution time
            next_execution = self._calculate_next_execution(schedule_frequency)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO backup_jobs (
                    job_id, name, asset_id, backup_type, source_location,
                    destination_location, schedule, retention_days,
                    compression_enabled, encryption_enabled, next_execution,
                    execution_results
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id, name, asset_id, backup_type.value, source_location,
                destination_location, schedule_frequency, retention_days,
                compression_enabled, encryption_enabled, next_execution,
                json.dumps([])
            ))
            
            conn.commit()
            conn.close()
            
            # Schedule the job
            self._schedule_backup_job(job_id, schedule_frequency)
            
            logger.info(f"Created backup job: {name} ({job_id})")
            return job_id
            
        except Exception as e:
            logger.error(f"Failed to create backup job {name}: {e}")
            return None
    
    def _calculate_next_execution(self, schedule_frequency: str) -> float:
        """Calculate next execution time based on schedule."""
        now = datetime.now()
        
        if schedule_frequency == "hourly":
            next_time = now + timedelta(hours=1)
        elif schedule_frequency == "daily":
            next_time = now + timedelta(days=1)
        elif schedule_frequency == "weekly":
            next_time = now + timedelta(weeks=1)
        elif schedule_frequency == "monthly":
            next_time = now + timedelta(days=30)  # Simplified
        else:
            next_time = now + timedelta(days=1)  # Default to daily
        
        return next_time.timestamp()
    
    def _schedule_backup_job(self, job_id: str, schedule_frequency: str) -> None:
        """Schedule a backup job using the schedule library."""
        def execute_job():
            asyncio.run(self.execute_backup_job(job_id))
        
        if schedule_frequency == "hourly":
            schedule.every().hour.do(execute_job)
        elif schedule_frequency == "daily":
            schedule.every().day.at("02:00").do(execute_job)  # Run at 2 AM
        elif schedule_frequency == "weekly":
            schedule.every().sunday.at("02:00").do(execute_job)  # Run Sunday at 2 AM
        elif schedule_frequency == "monthly":
            schedule.every(30).days.at("02:00").do(execute_job)  # Run every 30 days at 2 AM
    
    async def execute_backup_job(self, job_id: str) -> Dict[str, Any]:
        """Execute a backup job."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get job details
            cursor.execute("""
                SELECT * FROM backup_jobs WHERE job_id = ?
            """, (job_id,))
            
            row = cursor.fetchone()
            if not row:
                return {"error": "Backup job not found"}
            
            job = {
                "job_id": row[0],
                "name": row[1],
                "asset_id": row[2],
                "backup_type": row[3],
                "source_location": row[4],
                "destination_location": row[5],
                "schedule": row[6],
                "retention_days": row[7],
                "compression_enabled": bool(row[8]),
                "encryption_enabled": bool(row[9]),
                "enabled": bool(row[10]),
                "last_execution": row[11],
                "next_execution": row[12],
                "execution_results": json.loads(row[13] or "[]")
            }
            
            if not job["enabled"]:
                return {"error": "Backup job is disabled"}
            
            execution_time = time.time()
            execution_id = str(uuid.uuid4())
            
            # Execute backup (simplified implementation)
            logger.info(f"Starting backup job: {job['name']}")
            
            backup_result = await self._perform_backup(job)
            
            execution_result = {
                "execution_id": execution_id,
                "execution_time": execution_time,
                "status": backup_result.get("status", "failed"),
                "source_location": job["source_location"],
                "destination_location": job["destination_location"],
                "backup_size_bytes": backup_result.get("size_bytes", 0),
                "duration_seconds": backup_result.get("duration", 0),
                "compression_ratio": backup_result.get("compression_ratio", 1.0),
                "error_message": backup_result.get("error"),
                "backup_file_path": backup_result.get("backup_path")
            }
            
            # Update job with execution results
            next_execution = self._calculate_next_execution(job["schedule"])
            
            updated_results = job["execution_results"] + [execution_result]
            # Keep only last 100 results
            updated_results = updated_results[-100:]
            
            cursor.execute("""
                UPDATE backup_jobs 
                SET last_execution = ?, next_execution = ?, execution_results = ?
                WHERE job_id = ?
            """, (execution_time, next_execution, json.dumps(updated_results), job_id))
            
            conn.commit()
            conn.close()
            
            if backup_result.get("status") == "success":
                logger.info(f"Backup job {job['name']} completed successfully")
            else:
                logger.error(f"Backup job {job['name']} failed: {backup_result.get('error')}")
            
            return execution_result
            
        except Exception as e:
            logger.error(f"Failed to execute backup job {job_id}: {e}")
            return {"error": str(e)}
    
    async def _perform_backup(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the actual backup operation."""
        try:
            start_time = time.time()
            
            source_path = job["source_location"]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{job['name']}_{timestamp}.backup"
            
            if job["backup_type"] == "full":
                backup_path = os.path.join(self.backup_storage_path, backup_filename)
            else:
                # For incremental/differential, append timestamp to existing backup
                backup_path = os.path.join(self.backup_storage_path, f"{job['name']}_incremental_{timestamp}.backup")
            
            # Simplified backup operation (would be much more sophisticated in real implementation)
            if os.path.exists(source_path):
                if job["compression_enabled"]:
                    # Create compressed backup
                    with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        if os.path.isfile(source_path):
                            zipf.write(source_path, os.path.basename(source_path))
                        else:
                            for root, dirs, files in os.walk(source_path):
                                for file in files:
                                    file_path = os.path.join(root, file)
                                    arcname = os.path.relpath(file_path, source_path)
                                    zipf.write(file_path, arcname)
                    
                    compressed_size = os.path.getsize(backup_path)
                    original_size = self._get_directory_size(source_path)
                    compression_ratio = original_size / compressed_size if compressed_size > 0 else 1.0
                    
                else:
                    # Create uncompressed backup (copy files)
                    if os.path.isfile(source_path):
                        shutil.copy2(source_path, backup_path)
                    else:
                        shutil.copytree(source_path, backup_path, dirs_exist_ok=True)
                    
                    original_size = self._get_directory_size(source_path)
                    compression_ratio = 1.0
                
                duration = time.time() - start_time
                
                return {
                    "status": "success",
                    "size_bytes": os.path.getsize(backup_path),
                    "duration": duration,
                    "compression_ratio": compression_ratio,
                    "backup_path": backup_path
                }
            else:
                return {
                    "status": "failed",
                    "error": f"Source path does not exist: {source_path}",
                    "duration": time.time() - start_time
                }
                
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "duration": time.time() - start_time
            }
    
    def _get_directory_size(self, path: str) -> int:
        """Get total size of a directory or file."""
        total_size = 0
        try:
            if os.path.isfile(path):
                return os.path.getsize(path)
            else:
                for dirpath, dirnames, filenames in os.walk(path):
                    for filename in filenames:
                        filepath = os.path.join(dirpath, filename)
                        if os.path.exists(filepath):
                            total_size += os.path.getsize(filepath)
        except Exception as e:
            logger.error(f"Failed to get directory size for {path}: {e}")
        
        return total_size
    
    def get_backup_status(self, job_id: Optional[str] = None) -> Dict[str, Any]:
        """Get backup job status and recent executions."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if job_id:
                cursor.execute("SELECT * FROM backup_jobs WHERE job_id = ?", (job_id,))
            else:
                cursor.execute("SELECT * FROM backup_jobs")
            
            jobs = cursor.fetchall()
            conn.close()
            
            if job_id and not jobs:
                return {"error": "Backup job not found"}
            
            backup_status = {
                "timestamp": time.time(),
                "total_jobs": len(jobs),
                "enabled_jobs": sum(1 for job in jobs if job[10]),  # enabled column
                "jobs": []
            }
            
            for job in jobs:
                execution_results = json.loads(job[13] or "[]")
                last_execution = execution_results[-1] if execution_results else None
                
                job_status = {
                    "job_id": job[0],
                    "name": job[1],
                    "asset_id": job[2],
                    "backup_type": job[3],
                    "schedule": job[6],
                    "enabled": job[10],
                    "last_execution": job[11],
                    "next_execution": job[12],
                    "last_execution_status": last_execution.get("status") if last_execution else "never",
                    "total_executions": len(execution_results),
                    "successful_executions": sum(1 for r in execution_results if r.get("status") == "success"),
                    "failed_executions": sum(1 for r in execution_results if r.get("status") == "failed")
                }
                
                backup_status["jobs"].append(job_status)
            
            return backup_status
            
        except Exception as e:
            logger.error(f"Failed to get backup status: {e}")
            return {"error": str(e)}


class DisasterRecoveryManager:
    """
    Manages disaster recovery plans and testing.
    """
    
    def __init__(self, database_path: str = "data_governance.db"):
        self.db_path = database_path
        self.recovery_test_results: List[Dict[str, Any]] = []
    
    def create_disaster_recovery_plan(
        self,
        name: str,
        description: str,
        dr_tier: DisasterRecoveryTier,
        assets: List[str],
        rto_minutes: int,
        rpo_minutes: int,
        procedures: List[str],
        contacts: List[str],
        testing_schedule: str
    ) -> Optional[str]:
        """Create a new disaster recovery plan."""
        try:
            plan_id = str(uuid.uuid4())
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO disaster_recovery_plans (
                    plan_id, name, description, dr_tier, assets,
                    rto_minutes, rpo_minutes, procedures, contacts,
                    testing_schedule, test_results
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plan_id, name, description, dr_tier.value, json.dumps(assets),
                rto_minutes, rpo_minutes, json.dumps(procedures), json.dumps(contacts),
                testing_schedule, json.dumps({})
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Created disaster recovery plan: {name} ({plan_id})")
            return plan_id
            
        except Exception as e:
            logger.error(f"Failed to create disaster recovery plan {name}: {e}")
            return None
    
    async def execute_recovery_test(self, plan_id: str) -> Dict[str, Any]:
        """Execute a disaster recovery test."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get plan details
            cursor.execute("""
                SELECT * FROM disaster_recovery_plans WHERE plan_id = ?
            """, (plan_id,))
            
            row = cursor.fetchone()
            if not row:
                return {"error": "Recovery plan not found"}
            
            plan = {
                "plan_id": row[0],
                "name": row[1],
                "description": row[2],
                "dr_tier": row[3],
                "assets": json.loads(row[4]),
                "rto_minutes": row[5],
                "rpo_minutes": row[6],
                "procedures": json.loads(row[7]),
                "contacts": json.loads(row[8]),
                "testing_schedule": row[9],
                "last_tested": row[10],
                "test_results": json.loads(row[11] or "{}")
            }
            
            execution_time = time.time()
            test_id = str(uuid.uuid4())
            
            logger.info(f"Starting recovery test for plan: {plan['name']}")
            
            # Simulate recovery test execution
            test_result = await self._simulate_recovery_test(plan)
            
            # Update plan with test results
            new_test_results = plan["test_results"].copy()
            new_test_results[test_id] = {
                "execution_time": execution_time,
                "test_duration": test_result.get("duration", 0),
                "success": test_result.get("success", False),
                "procedures_completed": test_result.get("procedures_completed", 0),
                "total_procedures": test_result.get("total_procedures", 0),
                "issues_found": test_result.get("issues", []),
                "recommendations": test_result.get("recommendations", [])
            }
            
            cursor.execute("""
                UPDATE disaster_recovery_plans 
                SET last_tested = ?, test_results = ?
                WHERE plan_id = ?
            """, (execution_time, json.dumps(new_test_results), plan_id))
            
            conn.commit()
            conn.close()
            
            # Store in local cache
            self.recovery_test_results.append({
                "test_id": test_id,
                "plan_id": plan_id,
                "plan_name": plan["name"],
                "execution_time": execution_time,
                "result": test_result
            })
            
            if test_result.get("success"):
                logger.info(f"Recovery test for plan {plan['name']} completed successfully")
            else:
                logger.warning(f"Recovery test for plan {plan['name']} had issues")
            
            return {
                "test_id": test_id,
                "plan_name": plan["name"],
                "execution_time": execution_time,
                "test_result": test_result
            }
            
        except Exception as e:
            logger.error(f"Failed to execute recovery test for plan {plan_id}: {e}")
            return {"error": str(e)}
    
    async def _simulate_recovery_test(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate a disaster recovery test (simplified)."""
        start_time = time.time()
        
        try:
            total_procedures = len(plan["procedures"])
            completed_procedures = 0
            issues = []
            
            # Simulate procedure execution
            for i, procedure in enumerate(plan["procedures"]):
                # Simulate procedure execution time
                await asyncio.sleep(0.1)  # Short delay
                
                # Simulate random failures for some procedures
                import random
                if random.random() < 0.1:  # 10% chance of issue
                    issues.append(f"Procedure {i+1} had minor issues: {procedure}")
                else:
                    completed_procedures += 1
            
            duration = time.time() - start_time
            success = completed_procedures >= total_procedures * 0.8  # 80% success rate required
            
            recommendations = []
            if issues:
                recommendations.append("Review and fix identified issues in recovery procedures")
            if duration > plan["rto_minutes"] * 60:  # Convert minutes to seconds
                recommendations.append(f"Test took {duration/60:.1f} minutes, exceeds RTO of {plan['rto_minutes']} minutes")
            
            if not recommendations:
                recommendations.append("Recovery test passed successfully. Continue regular testing.")
            
            return {
                "success": success,
                "duration": duration,
                "procedures_completed": completed_procedures,
                "total_procedures": total_procedures,
                "issues": issues,
                "recommendations": recommendations
            }
            
        except Exception as e:
            return {
                "success": False,
                "duration": time.time() - start_time,
                "procedures_completed": 0,
                "total_procedures": len(plan["procedures"]),
                "issues": [f"Test execution failed: {str(e)}"],
                "recommendations": ["Fix test execution issues and rerun test"]
            }
    
    def get_disaster_recovery_status(self) -> Dict[str, Any]:
        """Get disaster recovery status for all plans."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM disaster_recovery_plans")
            plans = cursor.fetchall()
            conn.close()
            
            dr_status = {
                "timestamp": time.time(),
                "total_plans": len(plans),
                "plans": []
            }
            
            for plan in plans:
                test_results = json.loads(plan[11] or "{}")
                last_test = None
                if test_results:
                    latest_test_id = max(test_results.keys())
                    last_test = test_results[latest_test_id]
                
                plan_status = {
                    "plan_id": plan[0],
                    "name": plan[1],
                    "description": plan[2],
                    "dr_tier": plan[3],
                    "rto_minutes": plan[5],
                    "rpo_minutes": plan[6],
                    "testing_schedule": plan[9],
                    "last_tested": plan[10],
                    "assets_count": len(json.loads(plan[4])),
                    "procedures_count": len(json.loads(plan[7])),
                    "contacts_count": len(json.loads(plan[8])),
                    "has_recent_test": False,
                    "test_success_rate": 0.0,
                    "last_test_status": "never_tested"
                }
                
                if last_test:
                    plan_status["has_recent_test"] = (time.time() - last_test["execution_time"]) < (30 * 24 * 3600)  # 30 days
                    plan_status["test_success_rate"] = sum(1 for result in test_results.values() if result.get("success", False)) / len(test_results) * 100
                    plan_status["last_test_status"] = "success" if last_test.get("success", False) else "failed"
                
                dr_status["plans"].append(plan_status)
            
            return dr_status
            
        except Exception as e:
            logger.error(f"Failed to get disaster recovery status: {e}")
            return {"error": str(e)}
    
    def get_overdue_tests(self, max_age_days: int = 90) -> List[Dict[str, Any]]:
        """Get disaster recovery plans with overdue tests."""
        try:
            cutoff_time = time.time() - (max_age_days * 24 * 3600)
            dr_status = self.get_disaster_recovery_status()
            
            overdue_plans = []
            for plan in dr_status.get("plans", []):
                last_tested = plan.get("last_tested")
                if not last_tested or last_tested < cutoff_time:
                    overdue_plans.append({
                        "plan_id": plan["plan_id"],
                        "plan_name": plan["name"],
                        "dr_tier": plan["dr_tier"],
                        "last_tested": last_tested,
                        "days_since_test": (time.time() - last_tested) / (24 * 3600) if last_tested else float('inf'),
                        "testing_schedule": plan["testing_schedule"]
                    })
            
            return overdue_plans
            
        except Exception as e:
            logger.error(f"Failed to get overdue tests: {e}")
            return []


class EnterpriseDataGovernanceOrchestrator:
    """
    Main orchestrator for enterprise data governance.
    Integrates all data management components.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Initialize components
        self.asset_manager = DataAssetManager(
            self.config.get('database_path', 'data_governance.db')
        )
        self.quality_manager = DataQualityManager(
            self.config.get('database_path', 'data_governance.db')
        )
        self.backup_manager = BackupManager(
            self.config.get('database_path', 'data_governance.db')
        )
        self.dr_manager = DisasterRecoveryManager(
            self.config.get('database_path', 'data_governance.db')
        )
        
        # Initialize default data assets and rules
        self._initialize_default_data_governance()
        
        self.running = False
        self.governance_task = None
    
    def _initialize_default_data_governance(self) -> None:
        """Initialize default data governance framework."""
        
        # Register default data assets
        default_assets = [
            {
                "name": "User Authentication Database",
                "data_type": "database",
                "classification": DataClassification.CONFIDENTIAL,
                "owner": "IT Security",
                "steward": "Database Administrator",
                "location": "auth_db",
                "sensitivity_score": 9,
                "description": "Contains user credentials and authentication data"
            },
            {
                "name": "Application Logs",
                "data_type": "file_system",
                "classification": DataClassification.INTERNAL,
                "owner": "Operations",
                "steward": "DevOps Team",
                "location": "/var/log/app",
                "sensitivity_score": 3,
                "description": "Application and system logs"
            },
            {
                "name": "Customer Data Warehouse",
                "data_type": "database",
                "classification": DataClassification.RESTRICTED,
                "owner": "Data Analytics",
                "steward": "Data Steward",
                "location": "analytics_db",
                "sensitivity_score": 10,
                "description": "Aggregated customer analytics and reporting data"
            }
        ]
        
        for asset_config in default_assets:
            self.asset_manager.register_data_asset(**asset_config)
        
        # Add default data quality rules
        assets = self.asset_manager.get_data_assets()
        for asset in assets:
            if asset.data_type == "database":
                self.quality_manager.add_quality_rule(
                    asset_id=asset.asset_id,
                    rule_name=f"Completeness Check - {asset.name}",
                    rule_type="completeness",
                    rule_definition="SELECT COUNT(*) / (SELECT COUNT(*) FROM table) * 100 FROM table WHERE column IS NOT NULL",
                    severity="high",
                    threshold=0.95
                )
                
                self.quality_manager.add_quality_rule(
                    asset_id=asset.asset_id,
                    rule_name=f"Uniqueness Check - {asset.name}",
                    rule_type="uniqueness",
                    rule_definition="SELECT DISTINCT_COUNT / TOTAL_COUNT * 100 FROM table",
                    severity="medium",
                    threshold=0.98
                )
        
        # Create default backup jobs
        for asset in assets:
            if asset.classification in [DataClassification.CONFIDENTIAL, DataClassification.RESTRICTED]:
                self.backup_manager.create_backup_job(
                    name=f"Daily Backup - {asset.name}",
                    asset_id=asset.asset_id,
                    source_location=asset.location,
                    destination_location=f"backups/{asset.name}",
                    backup_type=BackupType.FULL,
                    schedule_frequency="daily",
                    retention_days=30,
                    compression_enabled=True,
                    encryption_enabled=True
                )
        
        # Create default disaster recovery plan
        sensitive_assets = self.asset_manager.get_sensitive_assets(min_sensitivity=8)
        if sensitive_assets:
            asset_ids = [asset.asset_id for asset in sensitive_assets]
            
            self.dr_manager.create_disaster_recovery_plan(
                name="Primary Database Disaster Recovery",
                description="Recovery plan for critical database assets",
                dr_tier=DisasterRecoveryTier.TIER_1,
                assets=asset_ids,
                rto_minutes=60,
                rpo_minutes=15,
                procedures=[
                    "Verify database server failure",
                    "Activate standby database server",
                    "Update DNS records to point to standby",
                    "Verify application connectivity",
                    "Run health checks on all services"
                ],
                contacts=["IT Security Manager", "Database Administrator", "Operations Lead"],
                testing_schedule="monthly"
            )
    
    async def run_data_governance_assessment(self) -> Dict[str, Any]:
        """Run comprehensive data governance assessment."""
        assessment_results = {
            "timestamp": time.time(),
            "data_assets": {},
            "data_quality": {},
            "backup_status": {},
            "disaster_recovery": {},
            "overall_score": 0.0,
            "critical_issues": [],
            "recommendations": []
        }
        
        # Assess data assets
        assets = self.asset_manager.get_data_assets()
        sensitive_assets = self.asset_manager.get_sensitive_assets()
        classification_volume = self.asset_manager.calculate_data_volume_by_classification()
        
        assessment_results["data_assets"] = {
            "total_assets": len(assets),
            "sensitive_assets": len(sensitive_assets),
            "classification_distribution": classification_volume,
            "high_risk_assets": len([a for a in assets if a.sensitivity_score >= 8])
        }
        
        # Assess data quality
        quality_trends = self.quality_manager.get_quality_trends()
        assessment_results["data_quality"] = quality_trends
        
        # Assess backup status
        backup_status = self.backup_manager.get_backup_status()
        assessment_results["backup_status"] = backup_status
        
        # Assess disaster recovery
        dr_status = self.dr_manager.get_disaster_recovery_status()
        overdue_tests = self.dr_manager.get_overdue_tests()
        
        assessment_results["disaster_recovery"] = {
            **dr_status,
            "overdue_tests": len(overdue_tests),
            "overdue_test_details": overdue_tests
        }
        
        # Calculate overall governance score
        scores = []
        
        # Asset classification score
        total_assets = len(assets)
        classified_assets = len([a for a in assets if a.classification != DataClassification.PUBLIC])
        asset_score = (classified_assets / total_assets * 100) if total_assets > 0 else 100
        scores.append(asset_score)
        
        # Data quality score
        quality_score = quality_trends.get("summary", {}).get("average_pass_rate", 0.0) * 100
        scores.append(quality_score)
        
        # Backup coverage score
        backup_coverage = (backup_status.get("enabled_jobs", 0) / max(backup_status.get("total_jobs", 1), 1)) * 100
        scores.append(backup_coverage)
        
        # Disaster recovery score
        dr_score = 100 - (len(overdue_tests) * 20)  # Deduct 20 points per overdue test
        scores.append(max(dr_score, 0))
        
        assessment_results["overall_score"] = sum(scores) / len(scores) if scores else 0
        
        # Identify critical issues
        if len([a for a in sensitive_assets if a.sensitivity_score >= 9]) > 0:
            assessment_results["critical_issues"].append("High-sensitivity assets without adequate protection")
        
        if quality_trends.get("summary", {}).get("average_pass_rate", 1.0) < 0.8:
            assessment_results["critical_issues"].append("Poor data quality across multiple assets")
        
        if backup_status.get("failed_executions", 0) > backup_status.get("successful_executions", 1):
            assessment_results["critical_issues"].append("Backup failure rate exceeds success rate")
        
        if len(overdue_tests) > 0:
            assessment_results["critical_issues"].append(f"{len(overdue_tests)} disaster recovery tests are overdue")
        
        # Generate recommendations
        recommendations = []
        
        if assessment_results["overall_score"] < 70:
            recommendations.append("Overall data governance score is below acceptable threshold. Comprehensive review needed.")
        
        for issue in assessment_results["critical_issues"]:
            if "high-sensitivity" in issue:
                recommendations.append("Implement additional security controls for high-sensitivity data assets")
            elif "data quality" in issue:
                recommendations.append("Review and fix data quality issues to improve reliability")
            elif "backup" in issue:
                recommendations.append("Investigate and resolve backup failures immediately")
            elif "disaster recovery" in issue:
                recommendations.append("Schedule overdue disaster recovery tests immediately")
        
        if not recommendations:
            recommendations.append("Data governance posture is good. Continue monitoring and regular assessments.")
        
        assessment_results["recommendations"] = recommendations
        
        return assessment_results
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get data governance system health information."""
        health = {
            "timestamp": time.time(),
            "governance_status": "active",
            "data_assets": {},
            "quality_metrics": {},
            "backup_health": {},
            "dr_health": {},
            "overall_healthy": True
        }
        
        try:
            # Data asset health
            assets = self.asset_manager.get_data_assets()
            sensitive_assets = self.asset_manager.get_sensitive_assets()
            
            health["data_assets"] = {
                "total": len(assets),
                "sensitive": len(sensitive_assets),
                "unclassified": len([a for a in assets if a.classification == DataClassification.PUBLIC])
            }
            
            # Quality metrics
            quality_trends = self.quality_manager.get_quality_trends()
            health["quality_metrics"] = {
                "average_pass_rate": quality_trends.get("summary", {}).get("average_pass_rate", 0.0),
                "total_executions": quality_trends.get("summary", {}).get("total_executions", 0)
            }
            
            # Backup health
            backup_status = self.backup_manager.get_backup_status()
            health["backup_health"] = {
                "total_jobs": backup_status.get("total_jobs", 0),
                "enabled_jobs": backup_status.get("enabled_jobs", 0),
                "success_rate": (
                    backup_status.get("jobs", [{}])[0].get("successful_executions", 0) /
                    max(backup_status.get("jobs", [{}])[0].get("total_executions", 1), 1) * 100
                    if backup_status.get("jobs") else 0
                )
            }
            
            # DR health
            dr_status = self.dr_manager.get_disaster_recovery_status()
            overdue_tests = self.dr_manager.get_overdue_tests()
            
            health["dr_health"] = {
                "total_plans": dr_status.get("total_plans", 0),
                "overdue_tests": len(overdue_tests),
                "last_test_age_days": min([
                    (time.time() - plan.get("last_tested", time.time())) / (24 * 3600)
                    for plan in dr_status.get("plans", []) if plan.get("last_tested")
                ]) if dr_status.get("plans") else float('inf')
            }
            
            # Overall health assessment
            issues = []
            if health["quality_metrics"]["average_pass_rate"] < 0.8:
                issues.append("Low data quality pass rate")
            if health["backup_health"]["success_rate"] < 80:
                issues.append("Poor backup success rate")
            if health["dr_health"]["overdue_tests"] > 0:
                issues.append("Overdue disaster recovery tests")
            
            health["overall_healthy"] = len(issues) == 0
            health["identified_issues"] = issues
            
        except Exception as e:
            logger.error(f"Failed to get data governance health: {e}")
            health["error"] = str(e)
            health["overall_healthy"] = False
        
        return health
    
    async def start_data_governance_monitoring(self) -> None:
        """Start data governance monitoring background tasks."""
        if self.running:
            logger.warning("Data governance monitoring already running")
            return
        
        self.running = True
        
        # Start background governance monitoring
        self.governance_task = asyncio.create_task(self._governance_monitoring_loop())
        
        logger.info("Enterprise data governance monitoring started")
    
    async def stop_data_governance_monitoring(self) -> None:
        """Stop data governance monitoring."""
        self.running = False
        
        if self.governance_task:
            self.governance_task.cancel()
            try:
                await self.governance_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Enterprise data governance monitoring stopped")
    
    async def _governance_monitoring_loop(self) -> None:
        """Background task for data governance monitoring."""
        while self.running:
            try:
                # Run periodic assessments (daily)
                assessment_results = await self.run_data_governance_assessment()
                
                if assessment_results["overall_score"] < 70:
                    logger.warning(f"Data governance score below threshold: {assessment_results['overall_score']:.1f}%")
                
                if assessment_results["critical_issues"]:
                    logger.warning(f"Found {len(assessment_results['critical_issues'])} critical data governance issues")
                
                # Check for backup failures
                backup_status = self.backup_manager.get_backup_status()
                for job in backup_status.get("jobs", []):
                    if job.get("failed_executions", 0) > job.get("successful_executions", 0):
                        logger.warning(f"Backup job {job['name']} has more failures than successes")
                
                # Check for overdue DR tests
                overdue_tests = self.dr_manager.get_overdue_tests()
                if overdue_tests:
                    logger.warning(f"Found {len(overdue_tests)} overdue disaster recovery tests")
                
                await asyncio.sleep(3600)  # Check every hour
                
            except Exception as e:
                logger.error(f"Error in data governance monitoring: {e}")
                await asyncio.sleep(3600)


# Global data governance orchestrator instance
enterprise_data_governance: Optional[EnterpriseDataGovernanceOrchestrator] = None


async def get_enterprise_data_governance(config: Optional[Dict[str, Any]] = None) -> EnterpriseDataGovernanceOrchestrator:
    """Get or create enterprise data governance orchestrator instance."""
    global enterprise_data_governance
    
    if enterprise_data_governance is None:
        enterprise_data_governance = EnterpriseDataGovernanceOrchestrator(config)
        await enterprise_data_governance.start_data_governance_monitoring()
    
    return enterprise_data_governance
