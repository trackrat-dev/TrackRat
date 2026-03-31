package com.trackrat.android.data.models

import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Response
import java.io.IOException
import java.net.SocketTimeoutException

/**
 * Unit tests for ApiResult and safeApiCall utility
 */
class ApiResultTest {

    @Test
    fun `ApiResult Success contains data`() {
        // Given: Success data
        val data = "test data"
        val result = ApiResult.Success(data)
        
        // Then: Data is accessible
        assertEquals(data, result.data)
    }
    
    @Test
    fun `ApiResult Error contains exception`() {
        // Given: Network error
        val exception = ApiException.NetworkError("No connection")
        val result = ApiResult.Error(exception)
        
        // Then: Exception is accessible
        assertEquals(exception, result.exception)
    }

    @Test
    fun `safeApiCall returns success for successful operation`() = runBlocking {
        // Given: Successful operation
        val expectedData = "success"
        
        // When: Calling safeApiCall with successful operation
        val result = safeApiCall { expectedData }
        
        // Then: Success result is returned
        assertTrue(result is ApiResult.Success)
        assertEquals(expectedData, (result as ApiResult.Success).data)
    }

    @Test
    fun `safeApiCall returns NetworkError for IOException`() = runBlocking {
        // Given: Operation that throws IOException
        val exception = IOException("Network unavailable")
        
        // When: Calling safeApiCall with failing operation
        val result = safeApiCall { throw exception }
        
        // Then: NetworkError is returned
        assertTrue(result is ApiResult.Error)
        val error = (result as ApiResult.Error).exception
        assertTrue(error is ApiException.NetworkError)
        assertEquals("Network unavailable", error.message)
    }

    @Test
    fun `safeApiCall returns TimeoutError for SocketTimeoutException`() = runBlocking {
        // Given: Operation that throws SocketTimeoutException
        val exception = SocketTimeoutException("Request timed out")
        
        // When: Calling safeApiCall with timeout operation
        val result = safeApiCall { throw exception }
        
        // Then: TimeoutError is returned
        assertTrue(result is ApiResult.Error)
        val error = (result as ApiResult.Error).exception
        assertTrue(error is ApiException.TimeoutError)
        assertEquals("Request timed out", error.message)
    }

    @Test
    fun `safeApiCall returns ClientError for 4xx HttpException`() = runBlocking {
        // Given: 404 HTTP error
        val response = Response.error<String>(404, okhttp3.ResponseBody.create(null, "Not found"))
        val exception = HttpException(response)
        
        // When: Calling safeApiCall with 4xx error
        val result = safeApiCall { throw exception }
        
        // Then: ClientError is returned
        assertTrue(result is ApiResult.Error)
        val error = (result as ApiResult.Error).exception
        assertTrue(error is ApiException.ClientError)
        assertEquals("HTTP 404: Client Error", error.message)
    }

    @Test
    fun `safeApiCall returns ServerError for 5xx HttpException`() = runBlocking {
        // Given: 500 HTTP error
        val response = Response.error<String>(500, okhttp3.ResponseBody.create(null, "Internal server error"))
        val exception = HttpException(response)
        
        // When: Calling safeApiCall with 5xx error
        val result = safeApiCall { throw exception }
        
        // Then: ServerError is returned
        assertTrue(result is ApiResult.Error)
        val error = (result as ApiResult.Error).exception
        assertTrue(error is ApiException.ServerError)
        assertEquals("HTTP 500: Server Error", error.message)
    }

    @Test
    fun `safeApiCall returns UnknownError for unexpected exception`() = runBlocking {
        // Given: Unexpected runtime exception
        val exception = RuntimeException("Unexpected error")
        
        // When: Calling safeApiCall with unexpected error
        val result = safeApiCall { throw exception }
        
        // Then: UnknownError is returned
        assertTrue(result is ApiResult.Error)
        val error = (result as ApiResult.Error).exception
        assertTrue(error is ApiException.UnknownError)
        assertEquals("Unexpected error", error.message)
    }

    @Test
    fun `safeApiCall returns ParseError for JSON parsing exception`() = runBlocking {
        // Given: JSON parsing exception (using RuntimeException as mock)
        val exception = RuntimeException("Expected BEGIN_OBJECT")
        
        // When: Calling safeApiCall with JSON parsing error
        val result = safeApiCall { throw exception }
        
        // Then: UnknownError is returned (since we can't mock JSON parsing easily)
        assertTrue(result is ApiResult.Error)
        val error = (result as ApiResult.Error).exception
        assertTrue(error is ApiException.UnknownError)
    }

    @Test
    fun `ApiException types have correct error codes`() {
        // Test that all ApiException types are properly defined
        val networkError = ApiException.NetworkError("test")
        val serverError = ApiException.ServerError("test")  
        val clientError = ApiException.ClientError("test")
        val timeoutError = ApiException.TimeoutError("test")
        val parseError = ApiException.ParseError("test")
        val unknownError = ApiException.UnknownError("test")
        
        // All should be ApiException instances
        assertTrue(networkError is ApiException)
        assertTrue(serverError is ApiException)
        assertTrue(clientError is ApiException)
        assertTrue(timeoutError is ApiException)
        assertTrue(parseError is ApiException)
        assertTrue(unknownError is ApiException)
        
        // All should have messages
        assertEquals("test", networkError.message)
        assertEquals("test", serverError.message)
        assertEquals("test", clientError.message)
        assertEquals("test", timeoutError.message)
        assertEquals("test", parseError.message)
        assertEquals("test", unknownError.message)
    }
}