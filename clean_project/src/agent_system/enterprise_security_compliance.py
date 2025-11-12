"""
Enterprise Security Compliance Automation Framework
Implements SOC2 Type II, ISO27001, and GDPR compliance automation
for enterprise-grade security and governance.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import hashlib
import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Set, Union
from enum import Enum
from datetime import datetime, timedelta
import uuid
import tempfile
import os
import subprocess

# Security libraries
try:
    import cryptography
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    import bcrypt
    import jwt
    import secrets
    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False

import sqlite3
import psutil

logger = logging.getLogger(__name__)


class ComplianceFramework(Enum):
    """Supported compliance frameworks."""
    SOC2_TYPE_II = "soc2_type_ii"
    ISO27001 = "iso27001"
    GDPR = "gdpr"
    HIPAA = "hipaa"
    NIST_CYBERSECURITY = "nist_cybersecurity"


class ControlStatus(Enum):
    """Security control implementation status."""
    IMPLEMENTED = "implemented"
    PARTIAL = "partial"
    NOT_IMPLEMENTED = "not_implemented"
    NOT_APPLICABLE = "not_applicable"


class RiskLevel(Enum):
    """Risk assessment levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"


@dataclass
class SecurityControl:
    """Individual security control definition."""
    control_id: str
    name: str
    description: str
    framework: ComplianceFramework
    category: str
    implementation_guidance: str
    testing_procedures: List[str]
    evidence_requirements: List[str]
    risk_level: RiskLevel
    status: ControlStatus = ControlStatus.NOT_IMPLEMENTED
    implementation_date: Optional[float] = None
    last_tested: Optional[float] = None
    test_results: Dict[str, Any] = field(default_factory=dict)
    owner: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComplianceEvidence:
    """Evidence for compliance controls."""
    evidence_id: str
    control_id: str
    evidence_type: str  # "document", "log", "screenshot", "configuration", etc.
    title: str
    description: str
    timestamp: float
    source: str  # Where the evidence was generated/collected
    file_path: Optional[str] = None
    content_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    validated: bool = False
    validation_date: Optional[float] = None
    validator: Optional[str] = None


@dataclass
class ComplianceAudit:
    """Compliance audit record."""
    audit_id: str
    framework: ComplianceFramework
    audit_type: str  # "internal", "external", "self_assessment"
    auditor: str
    start_date: float
    end_date: Optional[float] = None
    status: str = "in_progress"  # "in_progress", "completed", "failed"
    scope: List[str] = field(default_factory=list)
    findings: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    overall_score: Optional[float] = None
    certification_status: Optional[str] = None
    report_path: Optional[str] = None


@dataclass
class DataSubjectRights:
    """GDPR data subject rights request."""
    request_id: str
    subject_type: str  # "user", "employee", "customer"
    subject_identifier: str  # email, user_id, etc.
    request_type: str  # "access", "rectification", "erasure", "portability", "restriction", "objection"
    request_date: float
    due_date: float
    status: str = "pending"  # "pending", "processing", "completed", "rejected", "expired"
    requester_contact: Dict[str, str] = field(default_factory=dict)
    processing_notes: List[str] = field(default_factory=list)
    evidence_files: List[str] = field(default_factory=list)
    completion_date: Optional[float] = None
    validator: Optional[str] = None


class SecurityPolicyManager:
    """
    Manages security policies and ensures compliance with various frameworks.
    """
    
    def __init__(self, policy_database_path: str = "security_policies.db"):
        self.policy_db_path = policy_database_path
        self.policies: Dict[str, Dict[str, Any]] = {}
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize policy database."""
        try:
            conn = sqlite3.connect(self.policy_db_path)
            cursor = conn.cursor()
            
            # Create policies table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS policies (
                    policy_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    framework TEXT NOT NULL,
                    category TEXT NOT NULL,
                    version TEXT,
                    content TEXT,
                    effective_date REAL,
                    review_date REAL,
                    owner TEXT,
                    status TEXT DEFAULT 'draft',
                    metadata TEXT
                )
            """)
            
            # Create policy versions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS policy_versions (
                    version_id TEXT PRIMARY KEY,
                    policy_id TEXT NOT NULL,
                    version_number TEXT NOT NULL,
                    content TEXT NOT NULL,
                    change_description TEXT,
                    created_date REAL NOT NULL,
                    created_by TEXT,
                    FOREIGN KEY (policy_id) REFERENCES policies (policy_id)
                )
            """)
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to initialize policy database: {e}")
    
    def create_policy(
        self,
        policy_id: str,
        name: str,
        framework: ComplianceFramework,
        category: str,
        content: str,
        description: str = "",
        owner: str = "",
        effective_date: Optional[float] = None
    ) -> bool:
        """Create a new security policy."""
        try:
            if effective_date is None:
                effective_date = time.time()
            
            conn = sqlite3.connect(self.policy_db_path)
            cursor = conn.cursor()
            
            # Insert policy
            cursor.execute("""
                INSERT INTO policies (
                    policy_id, name, description, framework, category, 
                    content, effective_date, owner, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                policy_id, name, description, framework.value, category,
                content, effective_date, owner, "active"
            ))
            
            # Create initial version
            version_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO policy_versions (
                    version_id, policy_id, version_number, content, 
                    change_description, created_date, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                version_id, policy_id, "1.0", content,
                "Initial version", time.time(), owner
            ))
            
            conn.commit()
            conn.close()
            
            self.policies[policy_id] = {
                "name": name,
                "framework": framework.value,
                "category": category,
                "content": content,
                "status": "active",
                "effective_date": effective_date
            }
            
            logger.info(f"Created policy: {name} ({policy_id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create policy {policy_id}: {e}")
            return False
    
    def update_policy(
        self,
        policy_id: str,
        new_content: str,
        change_description: str,
        updated_by: str
    ) -> bool:
        """Update existing policy with new version."""
        try:
            conn = sqlite3.connect(self.policy_db_path)
            cursor = conn.cursor()
            
            # Get current version
            cursor.execute("""
                SELECT version_number FROM policy_versions 
                WHERE policy_id = ? ORDER BY created_date DESC LIMIT 1
            """, (policy_id,))
            
            result = cursor.fetchone()
            if not result:
                logger.error(f"Policy {policy_id} not found")
                return False
            
            current_version = result[0]
            # Simple version increment (could be more sophisticated)
            major, minor = current_version.split('.')
            new_version = f"{major}.{int(minor) + 1}"
            
            # Insert new version
            version_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO policy_versions (
                    version_id, policy_id, version_number, content, 
                    change_description, created_date, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                version_id, policy_id, new_version, new_content,
                change_description, time.time(), updated_by
            ))
            
            # Update policy content
            cursor.execute("""
                UPDATE policies SET content = ? WHERE policy_id = ?
            """, (new_content, policy_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Updated policy {policy_id} to version {new_version}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update policy {policy_id}: {e}")
            return False
    
    def get_policy(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """Get policy information."""
        try:
            conn = sqlite3.connect(self.policy_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT name, description, framework, category, content, 
                       version, effective_date, owner, status
                FROM policies WHERE policy_id = ?
            """, (policy_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    "policy_id": policy_id,
                    "name": result[0],
                    "description": result[1],
                    "framework": result[2],
                    "category": result[3],
                    "content": result[4],
                    "version": result[5],
                    "effective_date": result[6],
                    "owner": result[7],
                    "status": result[8]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get policy {policy_id}: {e}")
            return None
    
    def list_policies(self, framework: Optional[ComplianceFramework] = None) -> List[Dict[str, Any]]:
        """List all policies, optionally filtered by framework."""
        try:
            conn = sqlite3.connect(self.policy_db_path)
            cursor = conn.cursor()
            
            if framework:
                cursor.execute("""
                    SELECT policy_id, name, framework, category, status, effective_date
                    FROM policies WHERE framework = ?
                """, (framework.value,))
            else:
                cursor.execute("""
                    SELECT policy_id, name, framework, category, status, effective_date
                    FROM policies
                """)
            
            results = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "policy_id": row[0],
                    "name": row[1],
                    "framework": row[2],
                    "category": row[3],
                    "status": row[4],
                    "effective_date": row[5]
                }
                for row in results
            ]
            
        except Exception as e:
            logger.error(f"Failed to list policies: {e}")
            return []


class ComplianceControlManager:
    """
    Manages security controls and their implementation status.
    """
    
    def __init__(self, controls_database_path: str = "compliance_controls.db"):
        self.controls_db_path = controls_database_path
        self.controls: Dict[str, SecurityControl] = {}
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize controls database."""
        try:
            conn = sqlite3.connect(self.controls_db_path)
            cursor = conn.cursor()
            
            # Create controls table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS controls (
                    control_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    framework TEXT NOT NULL,
                    category TEXT NOT NULL,
                    implementation_guidance TEXT,
                    testing_procedures TEXT,
                    evidence_requirements TEXT,
                    risk_level TEXT NOT NULL,
                    status TEXT DEFAULT 'not_implemented',
                    implementation_date REAL,
                    last_tested REAL,
                    test_results TEXT,
                    owner TEXT,
                    metadata TEXT
                )
            """)
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to initialize controls database: {e}")
    
    def register_control(self, control: SecurityControl) -> bool:
        """Register a new security control."""
        try:
            conn = sqlite3.connect(self.controls_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO controls (
                    control_id, name, description, framework, category,
                    implementation_guidance, testing_procedures, evidence_requirements,
                    risk_level, status, implementation_date, last_tested,
                    test_results, owner, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                control.control_id, control.name, control.description,
                control.framework.value, control.category,
                control.implementation_guidance, json.dumps(control.testing_procedures),
                json.dumps(control.evidence_requirements), control.risk_level.value,
                control.status.value, control.implementation_date, control.last_tested,
                json.dumps(control.test_results), control.owner, json.dumps(control.metadata)
            ))
            
            conn.commit()
            conn.close()
            
            self.controls[control.control_id] = control
            logger.info(f"Registered control: {control.name} ({control.control_id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register control {control.control_id}: {e}")
            return False
    
    def update_control_status(
        self,
        control_id: str,
        status: ControlStatus,
        test_results: Optional[Dict[str, Any]] = None,
        tester: Optional[str] = None
    ) -> bool:
        """Update control implementation and test status."""
        try:
            conn = sqlite3.connect(self.controls_db_path)
            cursor = conn.cursor()
            
            update_data = {
                "status": status.value,
                "last_tested": time.time(),
                "test_results": json.dumps(test_results or {})
            }
            
            if status == ControlStatus.IMPLEMENTED:
                update_data["implementation_date"] = time.time()
            
            cursor.execute("""
                UPDATE controls SET 
                status = ?, last_tested = ?, test_results = ?
                WHERE control_id = ?
            """, (update_data["status"], update_data["last_tested"], 
                  update_data["test_results"], control_id))
            
            if control_id in self.controls:
                self.controls[control_id].status = status
                self.controls[control_id].last_tested = update_data["last_tested"]
                self.controls[control_id].test_results = test_results or {}
                
                if status == ControlStatus.IMPLEMENTED:
                    self.controls[control_id].implementation_date = update_data["implementation_date"]
            
            conn.commit()
            conn.close()
            
            logger.info(f"Updated control {control_id} status to {status.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update control {control_id}: {e}")
            return False
    
    def get_controls_by_framework(self, framework: ComplianceFramework) -> List[SecurityControl]:
        """Get all controls for a specific framework."""
        try:
            conn = sqlite3.connect(self.controls_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM controls WHERE framework = ?
            """, (framework.value,))
            
            results = cursor.fetchall()
            conn.close()
            
            controls = []
            for row in results:
                control = SecurityControl(
                    control_id=row[0],
                    name=row[1],
                    description=row[2],
                    framework=ComplianceFramework(row[3]),
                    category=row[4],
                    implementation_guidance=row[5],
                    testing_procedures=json.loads(row[6]),
                    evidence_requirements=json.loads(row[7]),
                    risk_level=RiskLevel(row[8]),
                    status=ControlStatus(row[9]),
                    implementation_date=row[10],
                    last_tested=row[11],
                    test_results=json.loads(row[12] or "{}"),
                    owner=row[13],
                    metadata=json.loads(row[14] or "{}")
                )
                controls.append(control)
            
            return controls
            
        except Exception as e:
            logger.error(f"Failed to get controls for framework {framework.value}: {e}")
            return []
    
    def get_compliance_score(self, framework: ComplianceFramework) -> float:
        """Calculate compliance score for a framework."""
        controls = self.get_controls_by_framework(framework)
        
        if not controls:
            return 0.0
        
        total_controls = len(controls)
        implemented_controls = sum(1 for c in controls if c.status == ControlStatus.IMPLEMENTED)
        partial_controls = sum(0.5 for c in controls if c.status == ControlStatus.PARTIAL)
        
        score = (implemented_controls + partial_controls) / total_controls * 100
        return min(score, 100.0)


class EvidenceCollectionManager:
    """
    Manages collection and validation of compliance evidence.
    """
    
    def __init__(self, evidence_database_path: str = "compliance_evidence.db"):
        self.evidence_db_path = evidence_database_path
        self.evidence_store_path = "evidence_store"
        self._initialize_database()
        self._create_evidence_directory()
    
    def _initialize_database(self) -> None:
        """Initialize evidence database."""
        try:
            conn = sqlite3.connect(self.evidence_db_path)
            cursor = conn.cursor()
            
            # Create evidence table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS evidence (
                    evidence_id TEXT PRIMARY KEY,
                    control_id TEXT NOT NULL,
                    evidence_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    timestamp REAL NOT NULL,
                    source TEXT NOT NULL,
                    file_path TEXT,
                    content_hash TEXT,
                    metadata TEXT,
                    validated BOOLEAN DEFAULT 0,
                    validation_date REAL,
                    validator TEXT,
                    FOREIGN KEY (control_id) REFERENCES controls (control_id)
                )
            """)
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to initialize evidence database: {e}")
    
    def _create_evidence_directory(self) -> None:
        """Create evidence storage directory."""
        try:
            os.makedirs(self.evidence_store_path, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create evidence directory: {e}")
    
    def collect_evidence(
        self,
        control_id: str,
        evidence_type: str,
        title: str,
        description: str,
        source: str,
        file_content: Optional[bytes] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Collect evidence for a control."""
        try:
            evidence_id = str(uuid.uuid4())
            
            file_path = None
            content_hash = None
            
            # Store file if content provided
            if file_content:
                file_path = os.path.join(self.evidence_store_path, f"{evidence_id}.dat")
                with open(file_path, 'wb') as f:
                    f.write(file_content)
                
                # Calculate content hash
                content_hash = hashlib.sha256(file_content).hexdigest()
            
            # Store metadata
            metadata_json = json.dumps(metadata or {})
            
            # Insert into database
            conn = sqlite3.connect(self.evidence_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO evidence (
                    evidence_id, control_id, evidence_type, title, description,
                    timestamp, source, file_path, content_hash, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                evidence_id, control_id, evidence_type, title, description,
                time.time(), source, file_path, content_hash, metadata_json
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Collected evidence: {title} ({evidence_id})")
            return evidence_id
            
        except Exception as e:
            logger.error(f"Failed to collect evidence: {e}")
            return None
    
    def validate_evidence(self, evidence_id: str, validator: str) -> bool:
        """Validate collected evidence."""
        try:
            conn = sqlite3.connect(self.evidence_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE evidence SET 
                validated = 1, validation_date = ?, validator = ?
                WHERE evidence_id = ?
            """, (time.time(), validator, evidence_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Validated evidence: {evidence_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to validate evidence {evidence_id}: {e}")
            return False
    
    def get_evidence_for_control(self, control_id: str) -> List[ComplianceEvidence]:
        """Get all evidence for a specific control."""
        try:
            conn = sqlite3.connect(self.evidence_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT evidence_id, evidence_type, title, description, timestamp,
                       source, file_path, content_hash, metadata, validated,
                       validation_date, validator
                FROM evidence WHERE control_id = ?
            """, (control_id,))
            
            results = cursor.fetchall()
            conn.close()
            
            evidence_list = []
            for row in results:
                evidence = ComplianceEvidence(
                    evidence_id=row[0],
                    control_id=control_id,
                    evidence_type=row[1],
                    title=row[2],
                    description=row[3],
                    timestamp=row[4],
                    source=row[5],
                    file_path=row[6],
                    content_hash=row[7],
                    metadata=json.loads(row[8] or "{}"),
                    validated=bool(row[9]),
                    validation_date=row[10],
                    validator=row[11]
                )
                evidence_list.append(evidence)
            
            return evidence_list
            
        except Exception as e:
            logger.error(f"Failed to get evidence for control {control_id}: {e}")
            return []
    
    def generate_evidence_report(self, control_id: str) -> Dict[str, Any]:
        """Generate evidence report for a control."""
        evidence_list = self.get_evidence_for_control(control_id)
        
        report = {
            "control_id": control_id,
            "total_evidence": len(evidence_list),
            "validated_evidence": sum(1 for e in evidence_list if e.validated),
            "evidence_by_type": {},
            "evidence_by_source": {},
            "validation_rate": 0.0,
            "evidence_details": []
        }
        
        if evidence_list:
            # Count by type and source
            for evidence in evidence_list:
                evidence_type = evidence.evidence_type
                source = evidence.source
                
                if evidence_type not in report["evidence_by_type"]:
                    report["evidence_by_type"][evidence_type] = 0
                report["evidence_by_type"][evidence_type] += 1
                
                if source not in report["evidence_by_source"]:
                    report["evidence_by_source"][source] = 0
                report["evidence_by_source"][source] += 1
            
            # Calculate validation rate
            report["validation_rate"] = (report["validated_evidence"] / len(evidence_list)) * 100
            
            # Add evidence details
            for evidence in evidence_list:
                report["evidence_details"].append({
                    "evidence_id": evidence.evidence_id,
                    "type": evidence.evidence_type,
                    "title": evidence.title,
                    "source": evidence.source,
                    "timestamp": evidence.timestamp,
                    "validated": evidence.validated,
                    "validator": evidence.validator
                })
        
        return report


class GDPRComplianceManager:
    """
    Manages GDPR compliance including data subject rights.
    """
    
    def __init__(self, gdpr_database_path: str = "gdpr_compliance.db"):
        self.gdpr_db_path = gdpr_database_path
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize GDPR compliance database."""
        try:
            conn = sqlite3.connect(self.gdpr_db_path)
            cursor = conn.cursor()
            
            # Create data subject requests table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_subject_requests (
                    request_id TEXT PRIMARY KEY,
                    subject_type TEXT NOT NULL,
                    subject_identifier TEXT NOT NULL,
                    request_type TEXT NOT NULL,
                    request_date REAL NOT NULL,
                    due_date REAL NOT NULL,
                    status TEXT DEFAULT 'pending',
                    requester_contact TEXT,
                    processing_notes TEXT,
                    evidence_files TEXT,
                    completion_date REAL,
                    validator TEXT
                )
            """)
            
            # Create data processing activities table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_processing_activities (
                    activity_id TEXT PRIMARY KEY,
                    purpose TEXT NOT NULL,
                    legal_basis TEXT NOT NULL,
                    data_categories TEXT NOT NULL,
                    data_sources TEXT NOT NULL,
                    recipients TEXT NOT NULL,
                    retention_period TEXT NOT NULL,
                    security_measures TEXT NOT NULL,
                    international_transfers TEXT,
                    dpo_contact TEXT,
                    created_date REAL NOT NULL
                )
            """)
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to initialize GDPR database: {e}")
    
    def create_data_subject_request(
        self,
        subject_type: str,
        subject_identifier: str,
        request_type: str,
        requester_contact: Dict[str, str]
    ) -> Optional[str]:
        """Create a new data subject rights request."""
        try:
            request_id = str(uuid.uuid4())
            request_date = time.time()
            
            # GDPR requires response within 30 days (can be extended to 90 for complex requests)
            due_date = request_date + (30 * 24 * 3600)  # 30 days
            
            conn = sqlite3.connect(self.gdpr_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO data_subject_requests (
                    request_id, subject_type, subject_identifier, request_type,
                    request_date, due_date, requester_contact
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                request_id, subject_type, subject_identifier, request_type,
                request_date, due_date, json.dumps(requester_contact)
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Created GDPR request: {request_type} for {subject_identifier}")
            return request_id
            
        except Exception as e:
            logger.error(f"Failed to create GDPR request: {e}")
            return None
    
    def process_access_request(self, request_id: str, data_export: Dict[str, Any]) -> bool:
        """Process data access request by providing data export."""
        try:
            evidence_id = str(uuid.uuid4())
            
            # Create export file
            export_file = f"gdpr_export_{request_id}.json"
            export_path = os.path.join("evidence_store", export_file)
            
            with open(export_path, 'w') as f:
                json.dump(data_export, f, indent=2)
            
            # Record processing
            conn = sqlite3.connect(self.gdpr_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE data_subject_requests 
                SET status = 'processing', 
                    processing_notes = COALESCE(processing_notes, '') || ?
                WHERE request_id = ?
            """, (f"Data export generated: {export_file}\n", request_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Processed access request: {request_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to process access request {request_id}: {e}")
            return False
    
    def process_erasure_request(self, request_id: str, verification_log: str) -> bool:
        """Process data erasure request."""
        try:
            conn = sqlite3.connect(self.gdpr_db_path)
            cursor = conn.cursor()
            
            # Check if erasure is legally required and possible
            # This is a simplified implementation - real implementation would need
            # careful legal analysis and automated data deletion systems
            
            cursor.execute("""
                UPDATE data_subject_requests 
                SET status = 'completed', 
                    completion_date = ?,
                    processing_notes = COALESCE(processing_notes, '') || ?
                WHERE request_id = ?
            """, (time.time(), f"Erasure completed: {verification_log}\n", request_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Processed erasure request: {request_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to process erasure request {request_id}: {e}")
            return False
    
    def get_pending_requests(self) -> List[DataSubjectRights]:
        """Get all pending GDPR requests."""
        try:
            conn = sqlite3.connect(self.gdpr_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT request_id, subject_type, subject_identifier, request_type,
                       request_date, due_date, status, requester_contact,
                       processing_notes, evidence_files, completion_date, validator
                FROM data_subject_requests 
                WHERE status IN ('pending', 'processing')
                ORDER BY due_date ASC
            """)
            
            results = cursor.fetchall()
            conn.close()
            
            requests = []
            for row in results:
                request = DataSubjectRights(
                    request_id=row[0],
                    subject_type=row[1],
                    subject_identifier=row[2],
                    request_type=row[3],
                    request_date=row[4],
                    due_date=row[5],
                    status=row[6],
                    requester_contact=json.loads(row[7] or "{}"),
                    processing_notes=row[8].split('\n') if row[8] else [],
                    evidence_files=json.loads(row[9] or "[]"),
                    completion_date=row[10],
                    validator=row[11]
                )
                requests.append(request)
            
            return requests
            
        except Exception as e:
            logger.error(f"Failed to get pending requests: {e}")
            return []
    
    def get_overdue_requests(self) -> List[DataSubjectRights]:
        """Get GDPR requests that are overdue for response."""
        current_time = time.time()
        pending_requests = self.get_pending_requests()
        
        overdue = []
        for request in pending_requests:
            if current_time > request.due_date:
                overdue.append(request)
        
        return overdue


class EnterpriseComplianceOrchestrator:
    """
    Main orchestrator for enterprise compliance automation.
    Integrates all compliance components and manages enterprise compliance lifecycle.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Initialize compliance components
        self.policy_manager = SecurityPolicyManager(
            self.config.get('policy_db_path', 'security_policies.db')
        )
        self.control_manager = ComplianceControlManager(
            self.config.get('controls_db_path', 'compliance_controls.db')
        )
        self.evidence_manager = EvidenceCollectionManager(
            self.config.get('evidence_db_path', 'compliance_evidence.db')
        )
        self.gdpr_manager = GDPRComplianceManager(
            self.config.get('gdpr_db_path', 'gdpr_compliance.db')
        )
        
        # Initialize default policies and controls
        self._initialize_default_compliance_framework()
        
        self.running = False
        self.compliance_task = None
    
    def _initialize_default_compliance_framework(self) -> None:
        """Initialize default SOC2 Type II controls and policies."""
        
        # Initialize SOC2 Type II controls
        soc2_controls = [
            SecurityControl(
                control_id="CC6.1",
                name="Logical and Physical Access Controls",
                description="The entity implements logical and physical access controls to restrict access to the system.",
                framework=ComplianceFramework.SOC2_TYPE_II,
                category="Security",
                implementation_guidance="Implement role-based access controls, multi-factor authentication, and network security controls.",
                testing_procedures=[
                    "Review access control matrix",
                    "Test MFA implementation",
                    "Review network security policies",
                    "Examine system access logs"
                ],
                evidence_requirements=[
                    "Access control documentation",
                    "MFA configuration screenshots",
                    "Network topology diagrams",
                    "System access logs"
                ],
                risk_level=RiskLevel.HIGH
            ),
            SecurityControl(
                control_id="CC6.2",
                name="System Operations",
                description="The entity manages the system's infrastructure and operations.",
                framework=ComplianceFramework.SOC2_TYPE_II,
                category="Security",
                implementation_guidance="Implement system monitoring, backup procedures, and incident response capabilities.",
                testing_procedures=[
                    "Review monitoring dashboards",
                    "Test backup and recovery procedures",
                    "Examine incident response procedures",
                    "Review system performance metrics"
                ],
                evidence_requirements=[
                    "Monitoring system screenshots",
                    "Backup procedure documentation",
                    "Incident response playbook",
                    "Performance metric reports"
                ],
                risk_level=RiskLevel.HIGH
            ),
            SecurityControl(
                control_id="CC7.1",
                name="System Monitoring",
                description="The entity monitors the system to detect security events.",
                framework=ComplianceFramework.SOC2_TYPE_II,
                category="Security",
                implementation_guidance="Implement comprehensive monitoring including security events, system performance, and user activities.",
                testing_procedures=[
                    "Review monitoring coverage",
                    "Test alert mechanisms",
                    "Examine log retention policies",
                    "Review incident detection procedures"
                ],
                evidence_requirements=[
                    "Monitoring coverage documentation",
                    "Alert configuration screenshots",
                    "Log retention policy",
                    "Incident detection procedures"
                ],
                risk_level=RiskLevel.MEDIUM
            )
        ]
        
        # Register controls
        for control in soc2_controls:
            self.control_manager.register_control(control)
        
        # Initialize basic policies
        self._create_default_policies()
    
    def _create_default_policies(self) -> None:
        """Create default security policies."""
        
        # Access Control Policy
        access_control_policy = """
# Access Control Policy

## Purpose
This policy establishes the standards for logical and physical access to the organization's systems and data.

## Scope
This policy applies to all employees, contractors, and third parties with access to organizational systems.

## Policy Statement
1. Access to systems and data shall be granted based on the principle of least privilege.
2. All user accounts must be authenticated using multi-factor authentication.
3. Access rights shall be reviewed quarterly.
4. All access attempts shall be logged and monitored.

## Responsibilities
- IT Security: Implement and maintain access controls
- Human Resources: Notify IT of employee status changes
- Department Managers: Approve access requests for their teams

## Enforcement
Violations of this policy may result in disciplinary action, up to and including termination.
        """
        
        self.policy_manager.create_policy(
            policy_id="POL-001",
            name="Access Control Policy",
            framework=ComplianceFramework.SOC2_TYPE_II,
            category="Security",
            content=access_control_policy,
            description="Policy for managing logical and physical access to systems",
            owner="IT Security"
        )
        
        # Data Protection Policy (GDPR compliance)
        data_protection_policy = """
# Data Protection Policy

## Purpose
This policy establishes the standards for personal data processing in compliance with GDPR and other applicable privacy regulations.

## Scope
This policy applies to all personal data processing activities within the organization.

## Policy Statement
1. Personal data shall be processed lawfully, fairly, and transparently.
2. Personal data shall be collected for specified, explicit, and legitimate purposes.
3. Personal data shall be accurate and kept up to date.
4. Personal data shall be kept no longer than necessary.
5. Data subjects shall be informed of their rights and how to exercise them.

## Rights of Data Subjects
- Right of access
- Right to rectification
- Right to erasure
- Right to data portability
- Right to object
- Right to restrict processing

## Enforcement
Violations of this policy may result in regulatory penalties and legal action.
        """
        
        self.policy_manager.create_policy(
            policy_id="POL-002",
            name="Data Protection Policy",
            framework=ComplianceFramework.GDPR,
            category="Privacy",
            content=data_protection_policy,
            description="Policy for personal data processing and GDPR compliance",
            owner="Data Protection Officer"
        )
    
    async def run_compliance_scan(self) -> Dict[str, Any]:
        """Run comprehensive compliance scan."""
        scan_results = {
            "timestamp": time.time(),
            "frameworks": {},
            "overall_compliance": 0.0,
            "critical_findings": [],
            "recommendations": []
        }
        
        # Scan each compliance framework
        for framework in ComplianceFramework:
            framework_score = self.control_manager.get_compliance_score(framework)
            controls = self.control_manager.get_controls_by_framework(framework)
            
            scan_results["frameworks"][framework.value] = {
                "score": framework_score,
                "total_controls": len(controls),
                "implemented_controls": sum(1 for c in controls if c.status == ControlStatus.IMPLEMENTED),
                "partial_controls": sum(1 for c in controls if c.status == ControlStatus.PARTIAL),
                "not_implemented_controls": sum(1 for c in controls if c.status == ControlStatus.NOT_IMPLEMENTED)
            }
            
            # Identify critical findings
            for control in controls:
                if control.risk_level == RiskLevel.CRITICAL and control.status != ControlStatus.IMPLEMENTED:
                    scan_results["critical_findings"].append({
                        "framework": framework.value,
                        "control_id": control.control_id,
                        "control_name": control.name,
                        "risk_level": control.risk_level.value,
                        "status": control.status.value
                    })
        
        # Calculate overall compliance score
        total_score = sum(fw["score"] for fw in scan_results["frameworks"].values())
        if scan_results["frameworks"]:
            scan_results["overall_compliance"] = total_score / len(scan_results["frameworks"])
        
        # Generate recommendations
        scan_results["recommendations"] = self._generate_compliance_recommendations(scan_results)
        
        return scan_results
    
    def _generate_compliance_recommendations(self, scan_results: Dict[str, Any]) -> List[str]:
        """Generate compliance improvement recommendations."""
        recommendations = []
        
        # Check overall compliance score
        if scan_results["overall_compliance"] < 70:
            recommendations.append("Overall compliance score is below acceptable threshold (70%). Immediate action required.")
        
        # Check for critical findings
        if scan_results["critical_findings"]:
            recommendations.append(f"{len(scan_results['critical_findings'])} critical controls are not implemented. Prioritize implementation.")
        
        # Framework-specific recommendations
        for framework, data in scan_results["frameworks"].items():
            if data["score"] < 60:
                recommendations.append(f"{framework} compliance score is critically low ({data['score']:.1f}%). Dedicated remediation needed.")
            
            not_implemented = data["not_implemented_controls"]
            if not_implemented > data["total_controls"] * 0.3:
                recommendations.append(f"{framework}: {not_implemented} controls not implemented. Review implementation priorities.")
        
        # GDPR-specific recommendations
        gdpr_data = scan_results["frameworks"].get("gdpr", {})
        if gdpr_data and gdpr_data["score"] < 80:
            recommendations.append("GDPR compliance requires improvement to avoid regulatory penalties.")
        
        if not recommendations:
            recommendations.append("Compliance posture is good. Continue monitoring and regular reviews.")
        
        return recommendations
    
    async def generate_compliance_report(self, framework: ComplianceFramework) -> Dict[str, Any]:
        """Generate comprehensive compliance report for a framework."""
        controls = self.control_manager.get_controls_by_framework(framework)
        
        report = {
            "framework": framework.value,
            "report_date": time.time(),
            "summary": {
                "total_controls": len(controls),
                "implemented": sum(1 for c in controls if c.status == ControlStatus.IMPLEMENTED),
                "partial": sum(1 for c in controls if c.status == ControlStatus.PARTIAL),
                "not_implemented": sum(1 for c in controls if c.status == ControlStatus.NOT_IMPLEMENTED),
                "compliance_score": self.control_manager.get_compliance_score(framework)
            },
            "control_details": [],
            "evidence_summary": {},
            "gaps": [],
            "recommendations": []
        }
        
        # Add control details
        for control in controls:
            evidence = self.evidence_manager.get_evidence_for_control(control.control_id)
            
            control_detail = {
                "control_id": control.control_id,
                "name": control.name,
                "status": control.status.value,
                "risk_level": control.risk_level.value,
                "evidence_count": len(evidence),
                "validation_rate": (sum(1 for e in evidence if e.validated) / len(evidence)) * 100 if evidence else 0,
                "last_tested": control.last_tested,
                "owner": control.owner
            }
            report["control_details"].append(control_detail)
            
            # Identify gaps
            if control.status != ControlStatus.IMPLEMENTED:
                report["gaps"].append({
                    "control_id": control.control_id,
                    "name": control.name,
                    "gap_description": f"Control status is {control.status.value}",
                    "priority": control.risk_level.value
                })
        
        # Add evidence summary
        for control in controls:
            evidence_report = self.evidence_manager.generate_evidence_report(control.control_id)
            report["evidence_summary"][control.control_id] = evidence_report
        
        # Add recommendations
        report["recommendations"] = self._generate_control_recommendations(controls)
        
        return report
    
    def _generate_control_recommendations(self, controls: List[SecurityControl]) -> List[str]:
        """Generate recommendations for control improvements."""
        recommendations = []
        
        # High-risk unimplemented controls
        high_risk_unimplemented = [
            c for c in controls 
            if c.risk_level == RiskLevel.HIGH and c.status != ControlStatus.IMPLEMENTED
        ]
        
        if high_risk_unimplemented:
            recommendations.append(
                f"Implement {len(high_risk_unimplemented)} high-risk controls immediately"
            )
        
        # Controls lacking evidence
        controls_without_evidence = [
            c for c in controls 
            if not self.evidence_manager.get_evidence_for_control(c.control_id)
        ]
        
        if controls_without_evidence:
            recommendations.append(
                f"Collect evidence for {len(controls_without_evidence)} controls"
            )
        
        # Controls not recently tested
        current_time = time.time()
        not_recently_tested = [
            c for c in controls
            if c.last_tested and (current_time - c.last_tested) > (90 * 24 * 3600)  # 90 days
        ]
        
        if not_recently_tested:
            recommendations.append(
                f"Retest {len(not_recently_tested)} controls that haven't been tested recently"
            )
        
        return recommendations
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get compliance system health information."""
        health = {
            "timestamp": time.time(),
            "compliance_status": "active",
            "frameworks_monitored": len(ComplianceFramework),
            "total_policies": len(self.policy_manager.policies),
            "total_controls": len(self.control_manager.controls),
            "framework_scores": {}
        }
        
        # Get compliance scores for each framework
        for framework in ComplianceFramework:
            score = self.control_manager.get_compliance_score(framework)
            health["framework_scores"][framework.value] = score
        
        # Check GDPR requests
        pending_gdpr = len(self.gdpr_manager.get_pending_requests())
        overdue_gdpr = len(self.gdpr_manager.get_overdue_requests())
        
        health["gdpr_requests"] = {
            "pending": pending_gdpr,
            "overdue": overdue_gdpr
        }
        
        # Overall health assessment
        avg_score = sum(health["framework_scores"].values()) / len(health["framework_scores"])
        health["overall_compliance_score"] = avg_score
        health["health_status"] = (
            "healthy" if avg_score >= 80 and overdue_gdpr == 0 else
            "warning" if avg_score >= 60 or overdue_gdpr > 0 else
            "critical"
        )
        
        return health
    
    async def start_compliance_monitoring(self) -> None:
        """Start compliance monitoring background tasks."""
        if self.running:
            logger.warning("Compliance monitoring already running")
            return
        
        self.running = True
        
        # Start background compliance monitoring
        self.compliance_task = asyncio.create_task(self._compliance_monitoring_loop())
        
        logger.info("Enterprise compliance monitoring started")
    
    async def stop_compliance_monitoring(self) -> None:
        """Stop compliance monitoring."""
        self.running = False
        
        if self.compliance_task:
            self.compliance_task.cancel()
            try:
                await self.compliance_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Enterprise compliance monitoring stopped")
    
    async def _compliance_monitoring_loop(self) -> None:
        """Background task for compliance monitoring."""
        while self.running:
            try:
                # Check for overdue GDPR requests
                overdue_requests = self.gdpr_manager.get_overdue_requests()
                if overdue_requests:
                    logger.warning(f"Found {len(overdue_requests)} overdue GDPR requests")
                
                # Run periodic compliance scans (daily)
                scan_results = await self.run_compliance_scan()
                if scan_results["overall_compliance"] < 70:
                    logger.warning(f"Compliance score below threshold: {scan_results['overall_compliance']:.1f}%")
                
                await asyncio.sleep(3600)  # Check every hour
                
            except Exception as e:
                logger.error(f"Error in compliance monitoring: {e}")
                await asyncio.sleep(3600)


# Global compliance orchestrator instance
enterprise_compliance: Optional[EnterpriseComplianceOrchestrator] = None


async def get_enterprise_compliance(config: Optional[Dict[str, Any]] = None) -> EnterpriseComplianceOrchestrator:
    """Get or create enterprise compliance orchestrator instance."""
    global enterprise_compliance
    
    if enterprise_compliance is None:
        enterprise_compliance = EnterpriseComplianceOrchestrator(config)
        await enterprise_compliance.start_compliance_monitoring()
    
    return enterprise_complianceEnterprise Security Compliance Automation Framework
Implements SOC2 Type II, ISO27001, and GDPR compliance automation
for enterprise-grade security and governance.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import hashlib
import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Set, Union
from enum import Enum
from datetime import datetime, timedelta
import uuid
import tempfile
import os
import subprocess

# Security libraries
try:
    import cryptography
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    import bcrypt
    import jwt
    import secrets
    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False

import sqlite3
import psutil

logger = logging.getLogger(__name__)


class ComplianceFramework(Enum):
    """Supported compliance frameworks."""
    SOC2_TYPE_II = "soc2_type_ii"
    ISO27001 = "iso27001"
    GDPR = "gdpr"
    HIPAA = "hipaa"
    NIST_CYBERSECURITY = "nist_cybersecurity"


class ControlStatus(Enum):
    """Security control implementation status."""
    IMPLEMENTED = "implemented"
    PARTIAL = "partial"
    NOT_IMPLEMENTED = "not_implemented"
    NOT_APPLICABLE = "not_applicable"


class RiskLevel(Enum):
    """Risk assessment levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"


@dataclass
class SecurityControl:
    """Individual security control definition."""
    control_id: str
    name: str
    description: str
    framework: ComplianceFramework
    category: str
    implementation_guidance: str
    testing_procedures: List[str]
    evidence_requirements: List[str]
    risk_level: RiskLevel
    status: ControlStatus = ControlStatus.NOT_IMPLEMENTED
    implementation_date: Optional[float] = None
    last_tested: Optional[float] = None
    test_results: Dict[str, Any] = field(default_factory=dict)
    owner: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComplianceEvidence:
    """Evidence for compliance controls."""
    evidence_id: str
    control_id: str
    evidence_type: str  # "document", "log", "screenshot", "configuration", etc.
    title: str
    description: str
    timestamp: float
    source: str  # Where the evidence was generated/collected
    file_path: Optional[str] = None
    content_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    validated: bool = False
    validation_date: Optional[float] = None
    validator: Optional[str] = None


@dataclass
class ComplianceAudit:
    """Compliance audit record."""
    audit_id: str
    framework: ComplianceFramework
    audit_type: str  # "internal", "external", "self_assessment"
    auditor: str
    start_date: float
    end_date: Optional[float] = None
    status: str = "in_progress"  # "in_progress", "completed", "failed"
    scope: List[str] = field(default_factory=list)
    findings: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    overall_score: Optional[float] = None
    certification_status: Optional[str] = None
    report_path: Optional[str] = None


@dataclass
class DataSubjectRights:
    """GDPR data subject rights request."""
    request_id: str
    subject_type: str  # "user", "employee", "customer"
    subject_identifier: str  # email, user_id, etc.
    request_type: str  # "access", "rectification", "erasure", "portability", "restriction", "objection"
    request_date: float
    due_date: float
    status: str = "pending"  # "pending", "processing", "completed", "rejected", "expired"
    requester_contact: Dict[str, str] = field(default_factory=dict)
    processing_notes: List[str] = field(default_factory=list)
    evidence_files: List[str] = field(default_factory=list)
    completion_date: Optional[float] = None
    validator: Optional[str] = None


class SecurityPolicyManager:
    """
    Manages security policies and ensures compliance with various frameworks.
    """
    
    def __init__(self, policy_database_path: str = "security_policies.db"):
        self.policy_db_path = policy_database_path
        self.policies: Dict[str, Dict[str, Any]] = {}
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize policy database."""
        try:
            conn = sqlite3.connect(self.policy_db_path)
            cursor = conn.cursor()
            
            # Create policies table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS policies (
                    policy_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    framework TEXT NOT NULL,
                    category TEXT NOT NULL,
                    version TEXT,
                    content TEXT,
                    effective_date REAL,
                    review_date REAL,
                    owner TEXT,
                    status TEXT DEFAULT 'draft',
                    metadata TEXT
                )
            """)
            
            # Create policy versions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS policy_versions (
                    version_id TEXT PRIMARY KEY,
                    policy_id TEXT NOT NULL,
                    version_number TEXT NOT NULL,
                    content TEXT NOT NULL,
                    change_description TEXT,
                    created_date REAL NOT NULL,
                    created_by TEXT,
                    FOREIGN KEY (policy_id) REFERENCES policies (policy_id)
                )
            """)
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to initialize policy database: {e}")
    
    def create_policy(
        self,
        policy_id: str,
        name: str,
        framework: ComplianceFramework,
        category: str,
        content: str,
        description: str = "",
        owner: str = "",
        effective_date: Optional[float] = None
    ) -> bool:
        """Create a new security policy."""
        try:
            if effective_date is None:
                effective_date = time.time()
            
            conn = sqlite3.connect(self.policy_db_path)
            cursor = conn.cursor()
            
            # Insert policy
            cursor.execute("""
                INSERT INTO policies (
                    policy_id, name, description, framework, category, 
                    content, effective_date, owner, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                policy_id, name, description, framework.value, category,
                content, effective_date, owner, "active"
            ))
            
            # Create initial version
            version_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO policy_versions (
                    version_id, policy_id, version_number, content, 
                    change_description, created_date, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                version_id, policy_id, "1.0", content,
                "Initial version", time.time(), owner
            ))
            
            conn.commit()
            conn.close()
            
            self.policies[policy_id] = {
                "name": name,
                "framework": framework.value,
                "category": category,
                "content": content,
                "status": "active",
                "effective_date": effective_date
            }
            
            logger.info(f"Created policy: {name} ({policy_id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create policy {policy_id}: {e}")
            return False
    
    def update_policy(
        self,
        policy_id: str,
        new_content: str,
        change_description: str,
        updated_by: str
    ) -> bool:
        """Update existing policy with new version."""
        try:
            conn = sqlite3.connect(self.policy_db_path)
            cursor = conn.cursor()
            
            # Get current version
            cursor.execute("""
                SELECT version_number FROM policy_versions 
                WHERE policy_id = ? ORDER BY created_date DESC LIMIT 1
            """, (policy_id,))
            
            result = cursor.fetchone()
            if not result:
                logger.error(f"Policy {policy_id} not found")
                return False
            
            current_version = result[0]
            # Simple version increment (could be more sophisticated)
            major, minor = current_version.split('.')
            new_version = f"{major}.{int(minor) + 1}"
            
            # Insert new version
            version_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO policy_versions (
                    version_id, policy_id, version_number, content, 
                    change_description, created_date, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                version_id, policy_id, new_version, new_content,
                change_description, time.time(), updated_by
            ))
            
            # Update policy content
            cursor.execute("""
                UPDATE policies SET content = ? WHERE policy_id = ?
            """, (new_content, policy_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Updated policy {policy_id} to version {new_version}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update policy {policy_id}: {e}")
            return False
    
    def get_policy(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """Get policy information."""
        try:
            conn = sqlite3.connect(self.policy_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT name, description, framework, category, content, 
                       version, effective_date, owner, status
                FROM policies WHERE policy_id = ?
            """, (policy_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    "policy_id": policy_id,
                    "name": result[0],
                    "description": result[1],
                    "framework": result[2],
                    "category": result[3],
                    "content": result[4],
                    "version": result[5],
                    "effective_date": result[6],
                    "owner": result[7],
                    "status": result[8]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get policy {policy_id}: {e}")
            return None
    
    def list_policies(self, framework: Optional[ComplianceFramework] = None) -> List[Dict[str, Any]]:
        """List all policies, optionally filtered by framework."""
        try:
            conn = sqlite3.connect(self.policy_db_path)
            cursor = conn.cursor()
            
            if framework:
                cursor.execute("""
                    SELECT policy_id, name, framework, category, status, effective_date
                    FROM policies WHERE framework = ?
                """, (framework.value,))
            else:
                cursor.execute("""
                    SELECT policy_id, name, framework, category, status, effective_date
                    FROM policies
                """)
            
            results = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "policy_id": row[0],
                    "name": row[1],
                    "framework": row[2],
                    "category": row[3],
                    "status": row[4],
                    "effective_date": row[5]
                }
                for row in results
            ]
            
        except Exception as e:
            logger.error(f"Failed to list policies: {e}")
            return []


class ComplianceControlManager:
    """
    Manages security controls and their implementation status.
    """
    
    def __init__(self, controls_database_path: str = "compliance_controls.db"):
        self.controls_db_path = controls_database_path
        self.controls: Dict[str, SecurityControl] = {}
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize controls database."""
        try:
            conn = sqlite3.connect(self.controls_db_path)
            cursor = conn.cursor()
            
            # Create controls table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS controls (
                    control_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    framework TEXT NOT NULL,
                    category TEXT NOT NULL,
                    implementation_guidance TEXT,
                    testing_procedures TEXT,
                    evidence_requirements TEXT,
                    risk_level TEXT NOT NULL,
                    status TEXT DEFAULT 'not_implemented',
                    implementation_date REAL,
                    last_tested REAL,
                    test_results TEXT,
                    owner TEXT,
                    metadata TEXT
                )
            """)
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to initialize controls database: {e}")
    
    def register_control(self, control: SecurityControl) -> bool:
        """Register a new security control."""
        try:
            conn = sqlite3.connect(self.controls_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO controls (
                    control_id, name, description, framework, category,
                    implementation_guidance, testing_procedures, evidence_requirements,
                    risk_level, status, implementation_date, last_tested,
                    test_results, owner, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                control.control_id, control.name, control.description,
                control.framework.value, control.category,
                control.implementation_guidance, json.dumps(control.testing_procedures),
                json.dumps(control.evidence_requirements), control.risk_level.value,
                control.status.value, control.implementation_date, control.last_tested,
                json.dumps(control.test_results), control.owner, json.dumps(control.metadata)
            ))
            
            conn.commit()
            conn.close()
            
            self.controls[control.control_id] = control
            logger.info(f"Registered control: {control.name} ({control.control_id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register control {control.control_id}: {e}")
            return False
    
    def update_control_status(
        self,
        control_id: str,
        status: ControlStatus,
        test_results: Optional[Dict[str, Any]] = None,
        tester: Optional[str] = None
    ) -> bool:
        """Update control implementation and test status."""
        try:
            conn = sqlite3.connect(self.controls_db_path)
            cursor = conn.cursor()
            
            update_data = {
                "status": status.value,
                "last_tested": time.time(),
                "test_results": json.dumps(test_results or {})
            }
            
            if status == ControlStatus.IMPLEMENTED:
                update_data["implementation_date"] = time.time()
            
            cursor.execute("""
                UPDATE controls SET 
                status = ?, last_tested = ?, test_results = ?
                WHERE control_id = ?
            """, (update_data["status"], update_data["last_tested"], 
                  update_data["test_results"], control_id))
            
            if control_id in self.controls:
                self.controls[control_id].status = status
                self.controls[control_id].last_tested = update_data["last_tested"]
                self.controls[control_id].test_results = test_results or {}
                
                if status == ControlStatus.IMPLEMENTED:
                    self.controls[control_id].implementation_date = update_data["implementation_date"]
            
            conn.commit()
            conn.close()
            
            logger.info(f"Updated control {control_id} status to {status.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update control {control_id}: {e}")
            return False
    
    def get_controls_by_framework(self, framework: ComplianceFramework) -> List[SecurityControl]:
        """Get all controls for a specific framework."""
        try:
            conn = sqlite3.connect(self.controls_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM controls WHERE framework = ?
            """, (framework.value,))
            
            results = cursor.fetchall()
            conn.close()
            
            controls = []
            for row in results:
                control = SecurityControl(
                    control_id=row[0],
                    name=row[1],
                    description=row[2],
                    framework=ComplianceFramework(row[3]),
                    category=row[4],
                    implementation_guidance=row[5],
                    testing_procedures=json.loads(row[6]),
                    evidence_requirements=json.loads(row[7]),
                    risk_level=RiskLevel(row[8]),
                    status=ControlStatus(row[9]),
                    implementation_date=row[10],
                    last_tested=row[11],
                    test_results=json.loads(row[12] or "{}"),
                    owner=row[13],
                    metadata=json.loads(row[14] or "{}")
                )
                controls.append(control)
            
            return controls
            
        except Exception as e:
            logger.error(f"Failed to get controls for framework {framework.value}: {e}")
            return []
    
    def get_compliance_score(self, framework: ComplianceFramework) -> float:
        """Calculate compliance score for a framework."""
        controls = self.get_controls_by_framework(framework)
        
        if not controls:
            return 0.0
        
        total_controls = len(controls)
        implemented_controls = sum(1 for c in controls if c.status == ControlStatus.IMPLEMENTED)
        partial_controls = sum(0.5 for c in controls if c.status == ControlStatus.PARTIAL)
        
        score = (implemented_controls + partial_controls) / total_controls * 100
        return min(score, 100.0)


class EvidenceCollectionManager:
    """
    Manages collection and validation of compliance evidence.
    """
    
    def __init__(self, evidence_database_path: str = "compliance_evidence.db"):
        self.evidence_db_path = evidence_database_path
        self.evidence_store_path = "evidence_store"
        self._initialize_database()
        self._create_evidence_directory()
    
    def _initialize_database(self) -> None:
        """Initialize evidence database."""
        try:
            conn = sqlite3.connect(self.evidence_db_path)
            cursor = conn.cursor()
            
            # Create evidence table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS evidence (
                    evidence_id TEXT PRIMARY KEY,
                    control_id TEXT NOT NULL,
                    evidence_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    timestamp REAL NOT NULL,
                    source TEXT NOT NULL,
                    file_path TEXT,
                    content_hash TEXT,
                    metadata TEXT,
                    validated BOOLEAN DEFAULT 0,
                    validation_date REAL,
                    validator TEXT,
                    FOREIGN KEY (control_id) REFERENCES controls (control_id)
                )
            """)
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to initialize evidence database: {e}")
    
    def _create_evidence_directory(self) -> None:
        """Create evidence storage directory."""
        try:
            os.makedirs(self.evidence_store_path, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create evidence directory: {e}")
    
    def collect_evidence(
        self,
        control_id: str,
        evidence_type: str,
        title: str,
        description: str,
        source: str,
        file_content: Optional[bytes] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Collect evidence for a control."""
        try:
            evidence_id = str(uuid.uuid4())
            
            file_path = None
            content_hash = None
            
            # Store file if content provided
            if file_content:
                file_path = os.path.join(self.evidence_store_path, f"{evidence_id}.dat")
                with open(file_path, 'wb') as f:
                    f.write(file_content)
                
                # Calculate content hash
                content_hash = hashlib.sha256(file_content).hexdigest()
            
            # Store metadata
            metadata_json = json.dumps(metadata or {})
            
            # Insert into database
            conn = sqlite3.connect(self.evidence_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO evidence (
                    evidence_id, control_id, evidence_type, title, description,
                    timestamp, source, file_path, content_hash, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                evidence_id, control_id, evidence_type, title, description,
                time.time(), source, file_path, content_hash, metadata_json
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Collected evidence: {title} ({evidence_id})")
            return evidence_id
            
        except Exception as e:
            logger.error(f"Failed to collect evidence: {e}")
            return None
    
    def validate_evidence(self, evidence_id: str, validator: str) -> bool:
        """Validate collected evidence."""
        try:
            conn = sqlite3.connect(self.evidence_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE evidence SET 
                validated = 1, validation_date = ?, validator = ?
                WHERE evidence_id = ?
            """, (time.time(), validator, evidence_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Validated evidence: {evidence_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to validate evidence {evidence_id}: {e}")
            return False
    
    def get_evidence_for_control(self, control_id: str) -> List[ComplianceEvidence]:
        """Get all evidence for a specific control."""
        try:
            conn = sqlite3.connect(self.evidence_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT evidence_id, evidence_type, title, description, timestamp,
                       source, file_path, content_hash, metadata, validated,
                       validation_date, validator
                FROM evidence WHERE control_id = ?
            """, (control_id,))
            
            results = cursor.fetchall()
            conn.close()
            
            evidence_list = []
            for row in results:
                evidence = ComplianceEvidence(
                    evidence_id=row[0],
                    control_id=control_id,
                    evidence_type=row[1],
                    title=row[2],
                    description=row[3],
                    timestamp=row[4],
                    source=row[5],
                    file_path=row[6],
                    content_hash=row[7],
                    metadata=json.loads(row[8] or "{}"),
                    validated=bool(row[9]),
                    validation_date=row[10],
                    validator=row[11]
                )
                evidence_list.append(evidence)
            
            return evidence_list
            
        except Exception as e:
            logger.error(f"Failed to get evidence for control {control_id}: {e}")
            return []
    
    def generate_evidence_report(self, control_id: str) -> Dict[str, Any]:
        """Generate evidence report for a control."""
        evidence_list = self.get_evidence_for_control(control_id)
        
        report = {
            "control_id": control_id,
            "total_evidence": len(evidence_list),
            "validated_evidence": sum(1 for e in evidence_list if e.validated),
            "evidence_by_type": {},
            "evidence_by_source": {},
            "validation_rate": 0.0,
            "evidence_details": []
        }
        
        if evidence_list:
            # Count by type and source
            for evidence in evidence_list:
                evidence_type = evidence.evidence_type
                source = evidence.source
                
                if evidence_type not in report["evidence_by_type"]:
                    report["evidence_by_type"][evidence_type] = 0
                report["evidence_by_type"][evidence_type] += 1
                
                if source not in report["evidence_by_source"]:
                    report["evidence_by_source"][source] = 0
                report["evidence_by_source"][source] += 1
            
            # Calculate validation rate
            report["validation_rate"] = (report["validated_evidence"] / len(evidence_list)) * 100
            
            # Add evidence details
            for evidence in evidence_list:
                report["evidence_details"].append({
                    "evidence_id": evidence.evidence_id,
                    "type": evidence.evidence_type,
                    "title": evidence.title,
                    "source": evidence.source,
                    "timestamp": evidence.timestamp,
                    "validated": evidence.validated,
                    "validator": evidence.validator
                })
        
        return report


class GDPRComplianceManager:
    """
    Manages GDPR compliance including data subject rights.
    """
    
    def __init__(self, gdpr_database_path: str = "gdpr_compliance.db"):
        self.gdpr_db_path = gdpr_database_path
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize GDPR compliance database."""
        try:
            conn = sqlite3.connect(self.gdpr_db_path)
            cursor = conn.cursor()
            
            # Create data subject requests table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_subject_requests (
                    request_id TEXT PRIMARY KEY,
                    subject_type TEXT NOT NULL,
                    subject_identifier TEXT NOT NULL,
                    request_type TEXT NOT NULL,
                    request_date REAL NOT NULL,
                    due_date REAL NOT NULL,
                    status TEXT DEFAULT 'pending',
                    requester_contact TEXT,
                    processing_notes TEXT,
                    evidence_files TEXT,
                    completion_date REAL,
                    validator TEXT
                )
            """)
            
            # Create data processing activities table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_processing_activities (
                    activity_id TEXT PRIMARY KEY,
                    purpose TEXT NOT NULL,
                    legal_basis TEXT NOT NULL,
                    data_categories TEXT NOT NULL,
                    data_sources TEXT NOT NULL,
                    recipients TEXT NOT NULL,
                    retention_period TEXT NOT NULL,
                    security_measures TEXT NOT NULL,
                    international_transfers TEXT,
                    dpo_contact TEXT,
                    created_date REAL NOT NULL
                )
            """)
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to initialize GDPR database: {e}")
    
    def create_data_subject_request(
        self,
        subject_type: str,
        subject_identifier: str,
        request_type: str,
        requester_contact: Dict[str, str]
    ) -> Optional[str]:
        """Create a new data subject rights request."""
        try:
            request_id = str(uuid.uuid4())
            request_date = time.time()
            
            # GDPR requires response within 30 days (can be extended to 90 for complex requests)
            due_date = request_date + (30 * 24 * 3600)  # 30 days
            
            conn = sqlite3.connect(self.gdpr_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO data_subject_requests (
                    request_id, subject_type, subject_identifier, request_type,
                    request_date, due_date, requester_contact
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                request_id, subject_type, subject_identifier, request_type,
                request_date, due_date, json.dumps(requester_contact)
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Created GDPR request: {request_type} for {subject_identifier}")
            return request_id
            
        except Exception as e:
            logger.error(f"Failed to create GDPR request: {e}")
            return None
    
    def process_access_request(self, request_id: str, data_export: Dict[str, Any]) -> bool:
        """Process data access request by providing data export."""
        try:
            evidence_id = str(uuid.uuid4())
            
            # Create export file
            export_file = f"gdpr_export_{request_id}.json"
            export_path = os.path.join("evidence_store", export_file)
            
            with open(export_path, 'w') as f:
                json.dump(data_export, f, indent=2)
            
            # Record processing
            conn = sqlite3.connect(self.gdpr_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE data_subject_requests 
                SET status = 'processing', 
                    processing_notes = COALESCE(processing_notes, '') || ?
                WHERE request_id = ?
            """, (f"Data export generated: {export_file}\n", request_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Processed access request: {request_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to process access request {request_id}: {e}")
            return False
    
    def process_erasure_request(self, request_id: str, verification_log: str) -> bool:
        """Process data erasure request."""
        try:
            conn = sqlite3.connect(self.gdpr_db_path)
            cursor = conn.cursor()
            
            # Check if erasure is legally required and possible
            # This is a simplified implementation - real implementation would need
            # careful legal analysis and automated data deletion systems
            
            cursor.execute("""
                UPDATE data_subject_requests 
                SET status = 'completed', 
                    completion_date = ?,
                    processing_notes = COALESCE(processing_notes, '') || ?
                WHERE request_id = ?
            """, (time.time(), f"Erasure completed: {verification_log}\n", request_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Processed erasure request: {request_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to process erasure request {request_id}: {e}")
            return False
    
    def get_pending_requests(self) -> List[DataSubjectRights]:
        """Get all pending GDPR requests."""
        try:
            conn = sqlite3.connect(self.gdpr_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT request_id, subject_type, subject_identifier, request_type,
                       request_date, due_date, status, requester_contact,
                       processing_notes, evidence_files, completion_date, validator
                FROM data_subject_requests 
                WHERE status IN ('pending', 'processing')
                ORDER BY due_date ASC
            """)
            
            results = cursor.fetchall()
            conn.close()
            
            requests = []
            for row in results:
                request = DataSubjectRights(
                    request_id=row[0],
                    subject_type=row[1],
                    subject_identifier=row[2],
                    request_type=row[3],
                    request_date=row[4],
                    due_date=row[5],
                    status=row[6],
                    requester_contact=json.loads(row[7] or "{}"),
                    processing_notes=row[8].split('\n') if row[8] else [],
                    evidence_files=json.loads(row[9] or "[]"),
                    completion_date=row[10],
                    validator=row[11]
                )
                requests.append(request)
            
            return requests
            
        except Exception as e:
            logger.error(f"Failed to get pending requests: {e}")
            return []
    
    def get_overdue_requests(self) -> List[DataSubjectRights]:
        """Get GDPR requests that are overdue for response."""
        current_time = time.time()
        pending_requests = self.get_pending_requests()
        
        overdue = []
        for request in pending_requests:
            if current_time > request.due_date:
                overdue.append(request)
        
        return overdue


class EnterpriseComplianceOrchestrator:
    """
    Main orchestrator for enterprise compliance automation.
    Integrates all compliance components and manages enterprise compliance lifecycle.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Initialize compliance components
        self.policy_manager = SecurityPolicyManager(
            self.config.get('policy_db_path', 'security_policies.db')
        )
        self.control_manager = ComplianceControlManager(
            self.config.get('controls_db_path', 'compliance_controls.db')
        )
        self.evidence_manager = EvidenceCollectionManager(
            self.config.get('evidence_db_path', 'compliance_evidence.db')
        )
        self.gdpr_manager = GDPRComplianceManager(
            self.config.get('gdpr_db_path', 'gdpr_compliance.db')
        )
        
        # Initialize default policies and controls
        self._initialize_default_compliance_framework()
        
        self.running = False
        self.compliance_task = None
    
    def _initialize_default_compliance_framework(self) -> None:
        """Initialize default SOC2 Type II controls and policies."""
        
        # Initialize SOC2 Type II controls
        soc2_controls = [
            SecurityControl(
                control_id="CC6.1",
                name="Logical and Physical Access Controls",
                description="The entity implements logical and physical access controls to restrict access to the system.",
                framework=ComplianceFramework.SOC2_TYPE_II,
                category="Security",
                implementation_guidance="Implement role-based access controls, multi-factor authentication, and network security controls.",
                testing_procedures=[
                    "Review access control matrix",
                    "Test MFA implementation",
                    "Review network security policies",
                    "Examine system access logs"
                ],
                evidence_requirements=[
                    "Access control documentation",
                    "MFA configuration screenshots",
                    "Network topology diagrams",
                    "System access logs"
                ],
                risk_level=RiskLevel.HIGH
            ),
            SecurityControl(
                control_id="CC6.2",
                name="System Operations",
                description="The entity manages the system's infrastructure and operations.",
                framework=ComplianceFramework.SOC2_TYPE_II,
                category="Security",
                implementation_guidance="Implement system monitoring, backup procedures, and incident response capabilities.",
                testing_procedures=[
                    "Review monitoring dashboards",
                    "Test backup and recovery procedures",
                    "Examine incident response procedures",
                    "Review system performance metrics"
                ],
                evidence_requirements=[
                    "Monitoring system screenshots",
                    "Backup procedure documentation",
                    "Incident response playbook",
                    "Performance metric reports"
                ],
                risk_level=RiskLevel.HIGH
            ),
            SecurityControl(
                control_id="CC7.1",
                name="System Monitoring",
                description="The entity monitors the system to detect security events.",
                framework=ComplianceFramework.SOC2_TYPE_II,
                category="Security",
                implementation_guidance="Implement comprehensive monitoring including security events, system performance, and user activities.",
                testing_procedures=[
                    "Review monitoring coverage",
                    "Test alert mechanisms",
                    "Examine log retention policies",
                    "Review incident detection procedures"
                ],
                evidence_requirements=[
                    "Monitoring coverage documentation",
                    "Alert configuration screenshots",
                    "Log retention policy",
                    "Incident detection procedures"
                ],
                risk_level=RiskLevel.MEDIUM
            )
        ]
        
        # Register controls
        for control in soc2_controls:
            self.control_manager.register_control(control)
        
        # Initialize basic policies
        self._create_default_policies()
    
    def _create_default_policies(self) -> None:
        """Create default security policies."""
        
        # Access Control Policy
        access_control_policy = """
# Access Control Policy

## Purpose
This policy establishes the standards for logical and physical access to the organization's systems and data.

## Scope
This policy applies to all employees, contractors, and third parties with access to organizational systems.

## Policy Statement
1. Access to systems and data shall be granted based on the principle of least privilege.
2. All user accounts must be authenticated using multi-factor authentication.
3. Access rights shall be reviewed quarterly.
4. All access attempts shall be logged and monitored.

## Responsibilities
- IT Security: Implement and maintain access controls
- Human Resources: Notify IT of employee status changes
- Department Managers: Approve access requests for their teams

## Enforcement
Violations of this policy may result in disciplinary action, up to and including termination.
        """
        
        self.policy_manager.create_policy(
            policy_id="POL-001",
            name="Access Control Policy",
            framework=ComplianceFramework.SOC2_TYPE_II,
            category="Security",
            content=access_control_policy,
            description="Policy for managing logical and physical access to systems",
            owner="IT Security"
        )
        
        # Data Protection Policy (GDPR compliance)
        data_protection_policy = """
# Data Protection Policy

## Purpose
This policy establishes the standards for personal data processing in compliance with GDPR and other applicable privacy regulations.

## Scope
This policy applies to all personal data processing activities within the organization.

## Policy Statement
1. Personal data shall be processed lawfully, fairly, and transparently.
2. Personal data shall be collected for specified, explicit, and legitimate purposes.
3. Personal data shall be accurate and kept up to date.
4. Personal data shall be kept no longer than necessary.
5. Data subjects shall be informed of their rights and how to exercise them.

## Rights of Data Subjects
- Right of access
- Right to rectification
- Right to erasure
- Right to data portability
- Right to object
- Right to restrict processing

## Enforcement
Violations of this policy may result in regulatory penalties and legal action.
        """
        
        self.policy_manager.create_policy(
            policy_id="POL-002",
            name="Data Protection Policy",
            framework=ComplianceFramework.GDPR,
            category="Privacy",
            content=data_protection_policy,
            description="Policy for personal data processing and GDPR compliance",
            owner="Data Protection Officer"
        )
    
    async def run_compliance_scan(self) -> Dict[str, Any]:
        """Run comprehensive compliance scan."""
        scan_results = {
            "timestamp": time.time(),
            "frameworks": {},
            "overall_compliance": 0.0,
            "critical_findings": [],
            "recommendations": []
        }
        
        # Scan each compliance framework
        for framework in ComplianceFramework:
            framework_score = self.control_manager.get_compliance_score(framework)
            controls = self.control_manager.get_controls_by_framework(framework)
            
            scan_results["frameworks"][framework.value] = {
                "score": framework_score,
                "total_controls": len(controls),
                "implemented_controls": sum(1 for c in controls if c.status == ControlStatus.IMPLEMENTED),
                "partial_controls": sum(1 for c in controls if c.status == ControlStatus.PARTIAL),
                "not_implemented_controls": sum(1 for c in controls if c.status == ControlStatus.NOT_IMPLEMENTED)
            }
            
            # Identify critical findings
            for control in controls:
                if control.risk_level == RiskLevel.CRITICAL and control.status != ControlStatus.IMPLEMENTED:
                    scan_results["critical_findings"].append({
                        "framework": framework.value,
                        "control_id": control.control_id,
                        "control_name": control.name,
                        "risk_level": control.risk_level.value,
                        "status": control.status.value
                    })
        
        # Calculate overall compliance score
        total_score = sum(fw["score"] for fw in scan_results["frameworks"].values())
        if scan_results["frameworks"]:
            scan_results["overall_compliance"] = total_score / len(scan_results["frameworks"])
        
        # Generate recommendations
        scan_results["recommendations"] = self._generate_compliance_recommendations(scan_results)
        
        return scan_results
    
    def _generate_compliance_recommendations(self, scan_results: Dict[str, Any]) -> List[str]:
        """Generate compliance improvement recommendations."""
        recommendations = []
        
        # Check overall compliance score
        if scan_results["overall_compliance"] < 70:
            recommendations.append("Overall compliance score is below acceptable threshold (70%). Immediate action required.")
        
        # Check for critical findings
        if scan_results["critical_findings"]:
            recommendations.append(f"{len(scan_results['critical_findings'])} critical controls are not implemented. Prioritize implementation.")
        
        # Framework-specific recommendations
        for framework, data in scan_results["frameworks"].items():
            if data["score"] < 60:
                recommendations.append(f"{framework} compliance score is critically low ({data['score']:.1f}%). Dedicated remediation needed.")
            
            not_implemented = data["not_implemented_controls"]
            if not_implemented > data["total_controls"] * 0.3:
                recommendations.append(f"{framework}: {not_implemented} controls not implemented. Review implementation priorities.")
        
        # GDPR-specific recommendations
        gdpr_data = scan_results["frameworks"].get("gdpr", {})
        if gdpr_data and gdpr_data["score"] < 80:
            recommendations.append("GDPR compliance requires improvement to avoid regulatory penalties.")
        
        if not recommendations:
            recommendations.append("Compliance posture is good. Continue monitoring and regular reviews.")
        
        return recommendations
    
    async def generate_compliance_report(self, framework: ComplianceFramework) -> Dict[str, Any]:
        """Generate comprehensive compliance report for a framework."""
        controls = self.control_manager.get_controls_by_framework(framework)
        
        report = {
            "framework": framework.value,
            "report_date": time.time(),
            "summary": {
                "total_controls": len(controls),
                "implemented": sum(1 for c in controls if c.status == ControlStatus.IMPLEMENTED),
                "partial": sum(1 for c in controls if c.status == ControlStatus.PARTIAL),
                "not_implemented": sum(1 for c in controls if c.status == ControlStatus.NOT_IMPLEMENTED),
                "compliance_score": self.control_manager.get_compliance_score(framework)
            },
            "control_details": [],
            "evidence_summary": {},
            "gaps": [],
            "recommendations": []
        }
        
        # Add control details
        for control in controls:
            evidence = self.evidence_manager.get_evidence_for_control(control.control_id)
            
            control_detail = {
                "control_id": control.control_id,
                "name": control.name,
                "status": control.status.value,
                "risk_level": control.risk_level.value,
                "evidence_count": len(evidence),
                "validation_rate": (sum(1 for e in evidence if e.validated) / len(evidence)) * 100 if evidence else 0,
                "last_tested": control.last_tested,
                "owner": control.owner
            }
            report["control_details"].append(control_detail)
            
            # Identify gaps
            if control.status != ControlStatus.IMPLEMENTED:
                report["gaps"].append({
                    "control_id": control.control_id,
                    "name": control.name,
                    "gap_description": f"Control status is {control.status.value}",
                    "priority": control.risk_level.value
                })
        
        # Add evidence summary
        for control in controls:
            evidence_report = self.evidence_manager.generate_evidence_report(control.control_id)
            report["evidence_summary"][control.control_id] = evidence_report
        
        # Add recommendations
        report["recommendations"] = self._generate_control_recommendations(controls)
        
        return report
    
    def _generate_control_recommendations(self, controls: List[SecurityControl]) -> List[str]:
        """Generate recommendations for control improvements."""
        recommendations = []
        
        # High-risk unimplemented controls
        high_risk_unimplemented = [
            c for c in controls 
            if c.risk_level == RiskLevel.HIGH and c.status != ControlStatus.IMPLEMENTED
        ]
        
        if high_risk_unimplemented:
            recommendations.append(
                f"Implement {len(high_risk_unimplemented)} high-risk controls immediately"
            )
        
        # Controls lacking evidence
        controls_without_evidence = [
            c for c in controls 
            if not self.evidence_manager.get_evidence_for_control(c.control_id)
        ]
        
        if controls_without_evidence:
            recommendations.append(
                f"Collect evidence for {len(controls_without_evidence)} controls"
            )
        
        # Controls not recently tested
        current_time = time.time()
        not_recently_tested = [
            c for c in controls
            if c.last_tested and (current_time - c.last_tested) > (90 * 24 * 3600)  # 90 days
        ]
        
        if not_recently_tested:
            recommendations.append(
                f"Retest {len(not_recently_tested)} controls that haven't been tested recently"
            )
        
        return recommendations
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get compliance system health information."""
        health = {
            "timestamp": time.time(),
            "compliance_status": "active",
            "frameworks_monitored": len(ComplianceFramework),
            "total_policies": len(self.policy_manager.policies),
            "total_controls": len(self.control_manager.controls),
            "framework_scores": {}
        }
        
        # Get compliance scores for each framework
        for framework in ComplianceFramework:
            score = self.control_manager.get_compliance_score(framework)
            health["framework_scores"][framework.value] = score
        
        # Check GDPR requests
        pending_gdpr = len(self.gdpr_manager.get_pending_requests())
        overdue_gdpr = len(self.gdpr_manager.get_overdue_requests())
        
        health["gdpr_requests"] = {
            "pending": pending_gdpr,
            "overdue": overdue_gdpr
        }
        
        # Overall health assessment
        avg_score = sum(health["framework_scores"].values()) / len(health["framework_scores"])
        health["overall_compliance_score"] = avg_score
        health["health_status"] = (
            "healthy" if avg_score >= 80 and overdue_gdpr == 0 else
            "warning" if avg_score >= 60 or overdue_gdpr > 0 else
            "critical"
        )
        
        return health
    
    async def start_compliance_monitoring(self) -> None:
        """Start compliance monitoring background tasks."""
        if self.running:
            logger.warning("Compliance monitoring already running")
            return
        
        self.running = True
        
        # Start background compliance monitoring
        self.compliance_task = asyncio.create_task(self._compliance_monitoring_loop())
        
        logger.info("Enterprise compliance monitoring started")
    
    async def stop_compliance_monitoring(self) -> None:
        """Stop compliance monitoring."""
        self.running = False
        
        if self.compliance_task:
            self.compliance_task.cancel()
            try:
                await self.compliance_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Enterprise compliance monitoring stopped")
    
    async def _compliance_monitoring_loop(self) -> None:
        """Background task for compliance monitoring."""
        while self.running:
            try:
                # Check for overdue GDPR requests
                overdue_requests = self.gdpr_manager.get_overdue_requests()
                if overdue_requests:
                    logger.warning(f"Found {len(overdue_requests)} overdue GDPR requests")
                
                # Run periodic compliance scans (daily)
                scan_results = await self.run_compliance_scan()
                if scan_results["overall_compliance"] < 70:
                    logger.warning(f"Compliance score below threshold: {scan_results['overall_compliance']:.1f}%")
                
                await asyncio.sleep(3600)  # Check every hour
                
            except Exception as e:
                logger.error(f"Error in compliance monitoring: {e}")
                await asyncio.sleep(3600)


# Global compliance orchestrator instance
enterprise_compliance: Optional[EnterpriseComplianceOrchestrator] = None


async def get_enterprise_compliance(config: Optional[Dict[str, Any]] = None) -> EnterpriseComplianceOrchestrator:
    """Get or create enterprise compliance orchestrator instance."""
    global enterprise_compliance
    
    if enterprise_compliance is None:
        enterprise_compliance = EnterpriseComplianceOrchestrator(config)
        await enterprise_compliance.start_compliance_monitoring()
    
    return enterprise_compliance
