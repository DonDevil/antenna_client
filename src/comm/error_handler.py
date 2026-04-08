"""Error handling for server responses according to handoff specifications."""

from __future__ import annotations

from typing import Dict, Any, Optional, Tuple
from enum import Enum

from utils.logger import get_logger


logger = get_logger(__name__)


class ErrorCode(str, Enum):
    """Server error codes per handoff section 10"""
    
    # Validation errors (HTTP 422)
    SCHEMA_VALIDATION_FAILED = "SCHEMA_VALIDATION_FAILED"
    FAMILY_NOT_SUPPORTED = "FAMILY_NOT_SUPPORTED"
    FAMILY_PROFILE_CONSTRAINT_FAILED = "FAMILY_PROFILE_CONSTRAINT_FAILED"
    INVALID_INTENT_REQUEST = "INVALID_INTENT_REQUEST"
    INVALID_CHAT_REQUEST = "INVALID_CHAT_REQUEST"
    V2_COMMAND_VALIDATION_FAILED = "V2_COMMAND_VALIDATION_FAILED"
    
    # Session/feedback errors
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    FEEDBACK_PROCESSING_FAILED = "FEEDBACK_PROCESSING_FAILED"
    
    # Surrogate/policy errors
    LOW_SURROGATE_CONFIDENCE = "LOW_SURROGATE_CONFIDENCE"
    
    # Unknown
    UNKNOWN = "UNKNOWN_ERROR"


class ErrorHandler:
    """Handle server errors with user-friendly messages and recovery suggestions"""
    
    # Maps error codes to (user_message, is_recoverable, suggested_action)
    ERROR_RESPONSES: Dict[str, Tuple[str, bool, str]] = {
        ErrorCode.SCHEMA_VALIDATION_FAILED: (
            "Request validation failed. Please check your inputs and try again.",
            True,
            "retry_with_form_check"
        ),
        ErrorCode.FAMILY_NOT_SUPPORTED: (
            "The selected antenna family is not supported by the server. "
            "Please choose a different family.",
            True,
            "select_different_family"
        ),
        ErrorCode.FAMILY_PROFILE_CONSTRAINT_FAILED: (
            "The antenna family does not support the specified frequency or bandwidth. "
            "Please adjust your design parameters.",
            True,
            "adjust_parameters"
        ),
        ErrorCode.INVALID_INTENT_REQUEST: (
            "The server could not parse your design request. "
            "Please rephrase your requirements more clearly.",
            True,
            "rephrase_request"
        ),
        ErrorCode.INVALID_CHAT_REQUEST: (
            "There was an issue with your chat message. "
            "Please try again with a different message.",
            True,
            "retry_chat"
        ),
        ErrorCode.V2_COMMAND_VALIDATION_FAILED: (
            "The server rejected the CST command package before execution. "
            "Please review the command contract details and retry.",
            True,
            "review_server_command_package"
        ),
        ErrorCode.SESSION_NOT_FOUND: (
            "The design session was not found on the server. "
            "The session may have expired. Please start a new design.",
            False,
            "start_new_session"
        ),
        ErrorCode.FEEDBACK_PROCESSING_FAILED: (
            "The server could not process your simulation results. "
            "Please try submitting again or start a new design.",
            True,
            "retry_feedback"
        ),
        ErrorCode.LOW_SURROGATE_CONFIDENCE: (
            "The server's confidence in the antenna prediction is too low. "
            "Try adjusting your design parameters or try a different frequency.",
            True,
            "adjust_parameters"
        ),
    }
    
    @staticmethod
    def parse_error(error_data: Dict[str, Any]) -> Tuple[ErrorCode, str, bool, str]:
        """Parse server error response
        
        Args:
            error_data: Error dict from server response
            
        Returns:
            Tuple of (error_code, user_message, is_recoverable, suggested_action)
        """
        try:
            # Extract error code from various possible locations
            error_code_str = (
                error_data.get("error_code") or
                error_data.get("code") or
                error_data.get("type") or
                "UNKNOWN_ERROR"
            )
            
            # Convert string to ErrorCode enum if possible
            try:
                error_code = ErrorCode(error_code_str)
            except ValueError:
                logger.warning(f"Unknown error code '{error_code_str}', treating as unknown")
                error_code = ErrorCode.UNKNOWN
            
            # Get server's error message
            server_message = error_data.get("message") or error_data.get("detail") or ""
            
            # Look up response configuration
            if error_code in ErrorHandler.ERROR_RESPONSES:
                user_msg, recoverable, action = ErrorHandler.ERROR_RESPONSES[error_code]
            else:
                # Fallback for unknown errors
                user_msg = f"An unexpected error occurred: {server_message or error_code_str}"
                recoverable = True
                action = "check_server_status"
            
            details = error_data.get("details") if isinstance(error_data.get("details"), dict) else None

            # Append server details if available
            if server_message and server_message not in user_msg:
                user_msg = f"{user_msg}\n\nDetails: {server_message}"
            if details:
                command_name = details.get("command_name")
                command_index = details.get("command_index")
                invalid_fields = details.get("invalid_fields")
                detail_parts = []
                if command_index is not None:
                    detail_parts.append(f"command_index={command_index}")
                if command_name:
                    detail_parts.append(f"command_name={command_name}")
                if invalid_fields:
                    detail_parts.append(f"invalid_fields={invalid_fields}")
                if detail_parts:
                    user_msg = f"{user_msg}\n\nValidation details: " + ", ".join(detail_parts)
            
            logger.warning(
                f"Error {error_code}: recoverable={recoverable}, action={action}"
            )
            
            return error_code, user_msg, recoverable, action
            
        except Exception as e:
            logger.error(f"Error parsing error response: {e}")
            return (
                ErrorCode.UNKNOWN,
                "An unexpected error occurred. Please try again.",
                True,
                "retry_operation"
            )
    
    @staticmethod
    def should_preserve_session(error_code: ErrorCode) -> bool:
        """Determine if session should be preserved after error
        
        Args:
            error_code: The error code
            
        Returns:
            True if session should be kept, False if should be cleared
        """
        # Preserve session for recoverable errors
        preserve_list = [
            ErrorCode.SCHEMA_VALIDATION_FAILED,
            ErrorCode.INVALID_INTENT_REQUEST,
            ErrorCode.INVALID_CHAT_REQUEST,
            ErrorCode.V2_COMMAND_VALIDATION_FAILED,
            ErrorCode.FEEDBACK_PROCESSING_FAILED,
            ErrorCode.LOW_SURROGATE_CONFIDENCE,
        ]
        return error_code in preserve_list
    
    @staticmethod
    def should_preserve_form_values(error_code: ErrorCode) -> bool:
        """Determine if form values should be preserved after error
        
        Args:
            error_code: The error code
            
        Returns:
            True if form values should be preserved for retry
        """
        # Preserve form for these errors
        preserve_list = [
            ErrorCode.SCHEMA_VALIDATION_FAILED,
            ErrorCode.INVALID_INTENT_REQUEST,
            ErrorCode.LOW_SURROGATE_CONFIDENCE,
        ]
        return error_code in preserve_list


class ErrorRecovery:
    """Utilities for recovering from errors"""
    
    @staticmethod
    def get_retry_guidance(error_code: ErrorCode, user_message: str) -> str:
        """Get user guidance for retrying after error
        
        Args:
            error_code: The error code
            user_message: User-friendly error message
            
        Returns:
            Guidance text for user
        """
        if error_code == ErrorCode.FAMILY_NOT_SUPPORTED:
            return "Supported antenna families: amc_patch, microstrip_patch, wban_patch"
        elif error_code == ErrorCode.FAMILY_PROFILE_CONSTRAINT_FAILED:
            return "Try adjusting frequency or bandwidth to values within the server's supported range."
        elif error_code == ErrorCode.SESSION_NOT_FOUND:
            return "Your session has been lost. You'll need to start a new design optimization."
        else:
            return "You can try again or start a new design."
