package com.trackrat.android.utils

import com.trackrat.android.data.models.ApiException

/**
 * Utility functions for error handling and categorization
 */
object ErrorUtils {
    
    /**
     * Check if an error is transient and likely to resolve itself
     */
    fun ApiException.isTransient(): Boolean {
        return when (this) {
            is ApiException.NetworkError -> true
            is ApiException.TimeoutError -> true
            is ApiException.ServerError -> code in 500..599 // Server errors may be transient
            is ApiException.ClientError -> false // Client errors are persistent
            is ApiException.ParseError -> false // Parse errors indicate API changes
            is ApiException.UnknownError -> false // Unknown errors are assumed persistent
        }
    }
    
    /**
     * Check if an error should stop auto-refresh completely
     */
    fun ApiException.shouldStopAutoRefresh(): Boolean {
        return when (this) {
            is ApiException.NetworkError -> false // Continue with network errors
            is ApiException.TimeoutError -> false // Continue with timeout errors  
            is ApiException.ServerError -> false // Continue but with delays
            is ApiException.ClientError -> true // Stop for client errors
            is ApiException.ParseError -> true // Stop for parse errors
            is ApiException.UnknownError -> true // Stop for unknown errors
        }
    }
    
    /**
     * Get user-friendly error message with action suggestions
     */
    fun ApiException.getUserFriendlyMessage(): String {
        return when (this) {
            is ApiException.NetworkError -> 
                "Check your internet connection and try again"
            is ApiException.TimeoutError -> 
                "Request timed out. Check your connection and try again"
            is ApiException.ServerError -> 
                "Server is temporarily unavailable. Please try again in a few minutes"
            is ApiException.ClientError -> when (code) {
                404 -> "Train not found. It may have been cancelled or the schedule changed"
                400 -> "Invalid request. Please check your selection and try again"
                else -> "Request failed. Please try again"
            }
            is ApiException.ParseError -> 
                "Unable to process server response. The app may need an update"
            is ApiException.UnknownError -> 
                "Something went wrong. Please try again"
        }
    }
    
    /**
     * Get appropriate retry delay for the error type (in milliseconds)
     */
    fun ApiException.getRetryDelay(): Long {
        return when (this) {
            is ApiException.NetworkError -> 3000L // 3 seconds
            is ApiException.TimeoutError -> 2000L // 2 seconds
            is ApiException.ServerError -> 5000L // 5 seconds
            is ApiException.ClientError -> 0L // Don't retry
            is ApiException.ParseError -> 1000L // 1 second (single retry)
            is ApiException.UnknownError -> 1000L // 1 second
        }
    }
    
    /**
     * Check if this error type allows for manual retry
     */
    fun ApiException.canRetry(): Boolean {
        return when (this) {
            is ApiException.NetworkError -> true
            is ApiException.TimeoutError -> true
            is ApiException.ServerError -> true
            is ApiException.ClientError -> code in 500..599 // Only retry server-like client errors
            is ApiException.ParseError -> true
            is ApiException.UnknownError -> true
        }
    }
    
    /**
     * Get icon resource for error type (if implementing error UI with icons)
     */
    fun ApiException.getErrorIcon(): String {
        return when (this) {
            is ApiException.NetworkError -> "wifi_off"
            is ApiException.TimeoutError -> "schedule"
            is ApiException.ServerError -> "cloud_off"
            is ApiException.ClientError -> "error_outline"
            is ApiException.ParseError -> "broken_image"
            is ApiException.UnknownError -> "help_outline"
        }
    }
}