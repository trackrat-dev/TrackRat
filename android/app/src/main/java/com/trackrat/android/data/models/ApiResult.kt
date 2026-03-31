package com.trackrat.android.data.models

/**
 * Sealed class representing API operation results
 * Provides structured error handling and prevents crashes
 */
sealed class ApiResult<out T> {
    /**
     * Successful API response
     */
    data class Success<T>(val data: T) : ApiResult<T>()
    
    /**
     * API operation failed
     */
    data class Error(val exception: ApiException) : ApiResult<Nothing>()
    
    /**
     * API operation is loading
     */
    data object Loading : ApiResult<Nothing>()
    
    /**
     * Helper method to check if result is successful
     */
    val isSuccess: Boolean get() = this is Success
    
    /**
     * Helper method to check if result has error
     */
    val isError: Boolean get() = this is Error
    
    /**
     * Helper method to check if result is loading
     */
    val isLoading: Boolean get() = this is Loading
    
    /**
     * Get data if successful, null otherwise
     */
    fun getDataOrNull(): T? = (this as? Success)?.data
    
    /**
     * Get exception if error, null otherwise
     */
    fun getErrorOrNull(): ApiException? = (this as? Error)?.exception
}

/**
 * Specific API exceptions with user-friendly messages
 */
sealed class ApiException(
    message: String,
    cause: Throwable? = null
) : Exception(message, cause) {
    
    /**
     * Network connectivity issues
     */
    data class NetworkError(
        override val message: String = "No internet connection. Please check your network and try again."
    ) : ApiException(message)
    
    /**
     * Server-side errors (5xx)
     */
    data class ServerError(
        val code: Int,
        override val message: String = "Server is temporarily unavailable. Please try again later."
    ) : ApiException(message)
    
    /**
     * Client-side errors (4xx)
     */
    data class ClientError(
        val code: Int,
        override val message: String = "Request failed. Please check your input and try again."
    ) : ApiException(message)
    
    /**
     * JSON parsing errors
     */
    data class ParseError(
        override val message: String = "Unable to process server response. Please try again."
    ) : ApiException(message)
    
    /**
     * Timeout errors
     */
    data class TimeoutError(
        override val message: String = "Request timed out. Please try again."
    ) : ApiException(message)
    
    /**
     * Unknown or unexpected errors
     */
    data class UnknownError(
        override val message: String = "Something went wrong. Please try again.",
        override val cause: Throwable?
    ) : ApiException(message, cause)
}

/**
 * Extension function to safely execute API calls
 */
inline fun <T> safeApiCall(action: () -> T): ApiResult<T> {
    return try {
        ApiResult.Success(action())
    } catch (e: Exception) {
        ApiResult.Error(e.toApiException())
    }
}

/**
 * Convert generic exceptions to specific API exceptions
 */
fun Throwable.toApiException(): ApiException {
    return when (this) {
        is java.net.UnknownHostException -> ApiException.NetworkError()
        is java.net.SocketTimeoutException -> ApiException.TimeoutError()
        is java.net.ConnectException -> ApiException.NetworkError()
        is retrofit2.HttpException -> {
            when (code()) {
                in 400..499 -> ApiException.ClientError(code(), "Request failed (${code()})")
                in 500..599 -> ApiException.ServerError(code(), "Server error (${code()})")
                else -> ApiException.UnknownError("HTTP error ${code()}", this)
            }
        }
        is com.squareup.moshi.JsonDataException,
        is com.squareup.moshi.JsonEncodingException -> ApiException.ParseError()
        else -> ApiException.UnknownError(cause = this)
    }
}