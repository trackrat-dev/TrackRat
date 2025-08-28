package com.trackrat.android.data.models;

/**
 * Sealed class representing API operation results
 * Provides structured error handling and prevents crashes
 */
@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000,\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0010\u000b\n\u0002\b\u0006\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\b6\u0018\u0000*\u0006\b\u0000\u0010\u0001 \u00012\u00020\u0002:\u0003\r\u000e\u000fB\u0007\b\u0004\u00a2\u0006\u0002\u0010\u0003J\r\u0010\t\u001a\u0004\u0018\u00018\u0000\u00a2\u0006\u0002\u0010\nJ\b\u0010\u000b\u001a\u0004\u0018\u00010\fR\u0011\u0010\u0004\u001a\u00020\u00058F\u00a2\u0006\u0006\u001a\u0004\b\u0004\u0010\u0006R\u0011\u0010\u0007\u001a\u00020\u00058F\u00a2\u0006\u0006\u001a\u0004\b\u0007\u0010\u0006R\u0011\u0010\b\u001a\u00020\u00058F\u00a2\u0006\u0006\u001a\u0004\b\b\u0010\u0006\u0082\u0001\u0003\u0010\u0011\u0012\u00a8\u0006\u0013"}, d2 = {"Lcom/trackrat/android/data/models/ApiResult;", "T", "", "()V", "isError", "", "()Z", "isLoading", "isSuccess", "getDataOrNull", "()Ljava/lang/Object;", "getErrorOrNull", "Lcom/trackrat/android/data/models/ApiException;", "Error", "Loading", "Success", "Lcom/trackrat/android/data/models/ApiResult$Error;", "Lcom/trackrat/android/data/models/ApiResult$Loading;", "Lcom/trackrat/android/data/models/ApiResult$Success;", "app_release"})
public abstract class ApiResult<T extends java.lang.Object> {
    
    private ApiResult() {
        super();
    }
    
    public final boolean isSuccess() {
        return false;
    }
    
    public final boolean isError() {
        return false;
    }
    
    public final boolean isLoading() {
        return false;
    }
    
    /**
     * Get data if successful, null otherwise
     */
    @org.jetbrains.annotations.Nullable()
    public final T getDataOrNull() {
        return null;
    }
    
    /**
     * Get exception if error, null otherwise
     */
    @org.jetbrains.annotations.Nullable()
    public final com.trackrat.android.data.models.ApiException getErrorOrNull() {
        return null;
    }
    
    /**
     * API operation failed
     */
    @kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000.\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0010\u0001\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0006\n\u0002\u0010\u000b\n\u0000\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\b\n\u0000\n\u0002\u0010\u000e\n\u0000\b\u0086\b\u0018\u00002\b\u0012\u0004\u0012\u00020\u00020\u0001B\r\u0012\u0006\u0010\u0003\u001a\u00020\u0004\u00a2\u0006\u0002\u0010\u0005J\t\u0010\b\u001a\u00020\u0004H\u00c6\u0003J\u0013\u0010\t\u001a\u00020\u00002\b\b\u0002\u0010\u0003\u001a\u00020\u0004H\u00c6\u0001J\u0013\u0010\n\u001a\u00020\u000b2\b\u0010\f\u001a\u0004\u0018\u00010\rH\u00d6\u0003J\t\u0010\u000e\u001a\u00020\u000fH\u00d6\u0001J\t\u0010\u0010\u001a\u00020\u0011H\u00d6\u0001R\u0011\u0010\u0003\u001a\u00020\u0004\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0006\u0010\u0007\u00a8\u0006\u0012"}, d2 = {"Lcom/trackrat/android/data/models/ApiResult$Error;", "Lcom/trackrat/android/data/models/ApiResult;", "", "exception", "Lcom/trackrat/android/data/models/ApiException;", "(Lcom/trackrat/android/data/models/ApiException;)V", "getException", "()Lcom/trackrat/android/data/models/ApiException;", "component1", "copy", "equals", "", "other", "", "hashCode", "", "toString", "", "app_release"})
    public static final class Error extends com.trackrat.android.data.models.ApiResult {
        @org.jetbrains.annotations.NotNull()
        private final com.trackrat.android.data.models.ApiException exception = null;
        
        public Error(@org.jetbrains.annotations.NotNull()
        com.trackrat.android.data.models.ApiException exception) {
        }
        
        @org.jetbrains.annotations.NotNull()
        public final com.trackrat.android.data.models.ApiException getException() {
            return null;
        }
        
        @org.jetbrains.annotations.NotNull()
        public final com.trackrat.android.data.models.ApiException component1() {
            return null;
        }
        
        @org.jetbrains.annotations.NotNull()
        public final com.trackrat.android.data.models.ApiResult.Error copy(@org.jetbrains.annotations.NotNull()
        com.trackrat.android.data.models.ApiException exception) {
            return null;
        }
        
        @java.lang.Override()
        public boolean equals(@org.jetbrains.annotations.Nullable()
        java.lang.Object other) {
            return false;
        }
        
        @java.lang.Override()
        public int hashCode() {
            return 0;
        }
        
        @java.lang.Override()
        @org.jetbrains.annotations.NotNull()
        public java.lang.String toString() {
            return null;
        }
    }
    
    /**
     * API operation is loading
     */
    @kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000(\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0010\u0001\n\u0002\b\u0002\n\u0002\u0010\u000b\n\u0000\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\b\n\u0000\n\u0002\u0010\u000e\n\u0000\b\u00c6\n\u0018\u00002\b\u0012\u0004\u0012\u00020\u00020\u0001B\u0007\b\u0002\u00a2\u0006\u0002\u0010\u0003J\u0013\u0010\u0004\u001a\u00020\u00052\b\u0010\u0006\u001a\u0004\u0018\u00010\u0007H\u00d6\u0003J\t\u0010\b\u001a\u00020\tH\u00d6\u0001J\t\u0010\n\u001a\u00020\u000bH\u00d6\u0001\u00a8\u0006\f"}, d2 = {"Lcom/trackrat/android/data/models/ApiResult$Loading;", "Lcom/trackrat/android/data/models/ApiResult;", "", "()V", "equals", "", "other", "", "hashCode", "", "toString", "", "app_release"})
    public static final class Loading extends com.trackrat.android.data.models.ApiResult {
        @org.jetbrains.annotations.NotNull()
        public static final com.trackrat.android.data.models.ApiResult.Loading INSTANCE = null;
        
        private Loading() {
        }
        
        @java.lang.Override()
        public boolean equals(@org.jetbrains.annotations.Nullable()
        java.lang.Object other) {
            return false;
        }
        
        @java.lang.Override()
        public int hashCode() {
            return 0;
        }
        
        @java.lang.Override()
        @org.jetbrains.annotations.NotNull()
        public java.lang.String toString() {
            return null;
        }
    }
    
    /**
     * Successful API response
     */
    @kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000&\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\t\n\u0002\u0010\u000b\n\u0000\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\b\n\u0000\n\u0002\u0010\u000e\n\u0000\b\u0086\b\u0018\u0000*\u0004\b\u0001\u0010\u00012\b\u0012\u0004\u0012\u0002H\u00010\u0002B\r\u0012\u0006\u0010\u0003\u001a\u00028\u0001\u00a2\u0006\u0002\u0010\u0004J\u000e\u0010\b\u001a\u00028\u0001H\u00c6\u0003\u00a2\u0006\u0002\u0010\u0006J\u001e\u0010\t\u001a\b\u0012\u0004\u0012\u00028\u00010\u00002\b\b\u0002\u0010\u0003\u001a\u00028\u0001H\u00c6\u0001\u00a2\u0006\u0002\u0010\nJ\u0013\u0010\u000b\u001a\u00020\f2\b\u0010\r\u001a\u0004\u0018\u00010\u000eH\u00d6\u0003J\t\u0010\u000f\u001a\u00020\u0010H\u00d6\u0001J\t\u0010\u0011\u001a\u00020\u0012H\u00d6\u0001R\u0013\u0010\u0003\u001a\u00028\u0001\u00a2\u0006\n\n\u0002\u0010\u0007\u001a\u0004\b\u0005\u0010\u0006\u00a8\u0006\u0013"}, d2 = {"Lcom/trackrat/android/data/models/ApiResult$Success;", "T", "Lcom/trackrat/android/data/models/ApiResult;", "data", "(Ljava/lang/Object;)V", "getData", "()Ljava/lang/Object;", "Ljava/lang/Object;", "component1", "copy", "(Ljava/lang/Object;)Lcom/trackrat/android/data/models/ApiResult$Success;", "equals", "", "other", "", "hashCode", "", "toString", "", "app_release"})
    public static final class Success<T extends java.lang.Object> extends com.trackrat.android.data.models.ApiResult<T> {
        private final T data = null;
        
        public Success(T data) {
        }
        
        public final T getData() {
            return null;
        }
        
        public final T component1() {
            return null;
        }
        
        @org.jetbrains.annotations.NotNull()
        public final com.trackrat.android.data.models.ApiResult.Success<T> copy(T data) {
            return null;
        }
        
        @java.lang.Override()
        public boolean equals(@org.jetbrains.annotations.Nullable()
        java.lang.Object other) {
            return false;
        }
        
        @java.lang.Override()
        public int hashCode() {
            return 0;
        }
        
        @java.lang.Override()
        @org.jetbrains.annotations.NotNull()
        public java.lang.String toString() {
            return null;
        }
    }
}