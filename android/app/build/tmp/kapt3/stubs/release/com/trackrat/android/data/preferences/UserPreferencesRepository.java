package com.trackrat.android.data.preferences;

import android.content.Context;
import androidx.datastore.core.DataStore;
import androidx.datastore.preferences.core.*;
import com.trackrat.android.utils.Constants;
import kotlinx.coroutines.flow.Flow;
import java.io.IOException;
import javax.inject.Inject;
import javax.inject.Singleton;

/**
 * Repository for managing user preferences using DataStore
 * Provides type-safe access to app preferences with Flow-based updates
 */
@javax.inject.Singleton()
@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000F\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u0002\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0007\n\u0002\u0010\u000b\n\u0002\b\b\n\u0002\u0010\t\n\u0002\b\u0005\b\u0007\u0018\u00002\u00020\u0001:\u0002$%B\u000f\b\u0007\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u00a2\u0006\u0002\u0010\u0004J \u0010\r\u001a\u00020\u000e2\u0006\u0010\u000f\u001a\u00020\u00102\b\u0010\u0011\u001a\u0004\u0018\u00010\u0010H\u0086@\u00a2\u0006\u0002\u0010\u0012J\u000e\u0010\u0013\u001a\u00020\u000eH\u0086@\u00a2\u0006\u0002\u0010\u0014J \u0010\u0015\u001a\u00020\u000e2\u0006\u0010\u000f\u001a\u00020\u00102\b\u0010\u0011\u001a\u0004\u0018\u00010\u0010H\u0086@\u00a2\u0006\u0002\u0010\u0012J\u0016\u0010\u0016\u001a\u00020\u000e2\u0006\u0010\u0017\u001a\u00020\u0018H\u0086@\u00a2\u0006\u0002\u0010\u0019J\u0016\u0010\u001a\u001a\u00020\u000e2\u0006\u0010\u0017\u001a\u00020\u0018H\u0086@\u00a2\u0006\u0002\u0010\u0019J\u0016\u0010\u001b\u001a\u00020\u000e2\u0006\u0010\u0017\u001a\u00020\u0018H\u0086@\u00a2\u0006\u0002\u0010\u0019J\u0016\u0010\u001c\u001a\u00020\u000e2\u0006\u0010\u001d\u001a\u00020\u0010H\u0086@\u00a2\u0006\u0002\u0010\u001eJ\u0018\u0010\u001f\u001a\u00020\u000e2\b\b\u0002\u0010 \u001a\u00020!H\u0086@\u00a2\u0006\u0002\u0010\"J \u0010#\u001a\u00020\u000e2\u0006\u0010\u000f\u001a\u00020\u00102\b\u0010\u0011\u001a\u0004\u0018\u00010\u0010H\u0086@\u00a2\u0006\u0002\u0010\u0012R\u000e\u0010\u0002\u001a\u00020\u0003X\u0082\u0004\u00a2\u0006\u0002\n\u0000R\u0014\u0010\u0005\u001a\b\u0012\u0004\u0012\u00020\u00070\u0006X\u0082\u0004\u00a2\u0006\u0002\n\u0000R\u0017\u0010\b\u001a\b\u0012\u0004\u0012\u00020\n0\t\u00a2\u0006\b\n\u0000\u001a\u0004\b\u000b\u0010\f\u00a8\u0006&"}, d2 = {"Lcom/trackrat/android/data/preferences/UserPreferencesRepository;", "", "context", "Landroid/content/Context;", "(Landroid/content/Context;)V", "dataStore", "Landroidx/datastore/core/DataStore;", "Landroidx/datastore/preferences/core/Preferences;", "userPreferencesFlow", "Lkotlinx/coroutines/flow/Flow;", "Lcom/trackrat/android/data/preferences/UserPreferencesRepository$UserPreferences;", "getUserPreferencesFlow", "()Lkotlinx/coroutines/flow/Flow;", "addFavoriteRoute", "", "fromStation", "", "toStation", "(Ljava/lang/String;Ljava/lang/String;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "clearAllPreferences", "(Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "removeFavoriteRoute", "setAutoRefreshEnabled", "enabled", "", "(ZLkotlin/coroutines/Continuation;)Ljava/lang/Object;", "setHapticFeedbackEnabled", "setNotificationEnabled", "setThemeMode", "themeMode", "(Ljava/lang/String;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "updateLastRefreshTime", "timestamp", "", "(JLkotlin/coroutines/Continuation;)Ljava/lang/Object;", "updateLastStations", "PreferencesKeys", "UserPreferences", "app_release"})
public final class UserPreferencesRepository {
    @org.jetbrains.annotations.NotNull()
    private final android.content.Context context = null;
    @org.jetbrains.annotations.NotNull()
    private final androidx.datastore.core.DataStore<androidx.datastore.preferences.core.Preferences> dataStore = null;
    
    /**
     * Flow of user preferences that emits when preferences change
     */
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.Flow<com.trackrat.android.data.preferences.UserPreferencesRepository.UserPreferences> userPreferencesFlow = null;
    
    @javax.inject.Inject()
    public UserPreferencesRepository(@org.jetbrains.annotations.NotNull()
    android.content.Context context) {
        super();
    }
    
    /**
     * Flow of user preferences that emits when preferences change
     */
    @org.jetbrains.annotations.NotNull()
    public final kotlinx.coroutines.flow.Flow<com.trackrat.android.data.preferences.UserPreferencesRepository.UserPreferences> getUserPreferencesFlow() {
        return null;
    }
    
    /**
     * Save last selected stations for quick access
     */
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Object updateLastStations(@org.jetbrains.annotations.NotNull()
    java.lang.String fromStation, @org.jetbrains.annotations.Nullable()
    java.lang.String toStation, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super kotlin.Unit> $completion) {
        return null;
    }
    
    /**
     * Toggle auto-refresh preference
     */
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Object setAutoRefreshEnabled(boolean enabled, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super kotlin.Unit> $completion) {
        return null;
    }
    
    /**
     * Toggle haptic feedback preference
     */
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Object setHapticFeedbackEnabled(boolean enabled, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super kotlin.Unit> $completion) {
        return null;
    }
    
    /**
     * Update theme mode preference
     */
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Object setThemeMode(@org.jetbrains.annotations.NotNull()
    java.lang.String themeMode, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super kotlin.Unit> $completion) {
        return null;
    }
    
    /**
     * Toggle notifications preference
     */
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Object setNotificationEnabled(boolean enabled, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super kotlin.Unit> $completion) {
        return null;
    }
    
    /**
     * Update last refresh time
     */
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Object updateLastRefreshTime(long timestamp, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super kotlin.Unit> $completion) {
        return null;
    }
    
    /**
     * Add route to favorites
     */
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Object addFavoriteRoute(@org.jetbrains.annotations.NotNull()
    java.lang.String fromStation, @org.jetbrains.annotations.Nullable()
    java.lang.String toStation, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super kotlin.Unit> $completion) {
        return null;
    }
    
    /**
     * Remove route from favorites
     */
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Object removeFavoriteRoute(@org.jetbrains.annotations.NotNull()
    java.lang.String fromStation, @org.jetbrains.annotations.Nullable()
    java.lang.String toStation, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super kotlin.Unit> $completion) {
        return null;
    }
    
    /**
     * Clear all preferences (useful for testing or reset functionality)
     */
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Object clearAllPreferences(@org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super kotlin.Unit> $completion) {
        return null;
    }
    
    @kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000,\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0010\u000b\n\u0002\b\u0003\n\u0002\u0010\"\n\u0002\u0010\u000e\n\u0002\b\u0006\n\u0002\u0010\t\n\u0002\b\b\b\u00c2\u0002\u0018\u00002\u00020\u0001B\u0007\b\u0002\u00a2\u0006\u0002\u0010\u0002R\u0017\u0010\u0003\u001a\b\u0012\u0004\u0012\u00020\u00050\u0004\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0006\u0010\u0007R\u001d\u0010\b\u001a\u000e\u0012\n\u0012\b\u0012\u0004\u0012\u00020\n0\t0\u0004\u00a2\u0006\b\n\u0000\u001a\u0004\b\u000b\u0010\u0007R\u0017\u0010\f\u001a\b\u0012\u0004\u0012\u00020\u00050\u0004\u00a2\u0006\b\n\u0000\u001a\u0004\b\r\u0010\u0007R\u0017\u0010\u000e\u001a\b\u0012\u0004\u0012\u00020\n0\u0004\u00a2\u0006\b\n\u0000\u001a\u0004\b\u000f\u0010\u0007R\u0017\u0010\u0010\u001a\b\u0012\u0004\u0012\u00020\u00110\u0004\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0012\u0010\u0007R\u0017\u0010\u0013\u001a\b\u0012\u0004\u0012\u00020\n0\u0004\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0014\u0010\u0007R\u0017\u0010\u0015\u001a\b\u0012\u0004\u0012\u00020\u00050\u0004\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0016\u0010\u0007R\u0017\u0010\u0017\u001a\b\u0012\u0004\u0012\u00020\n0\u0004\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0018\u0010\u0007\u00a8\u0006\u0019"}, d2 = {"Lcom/trackrat/android/data/preferences/UserPreferencesRepository$PreferencesKeys;", "", "()V", "AUTO_REFRESH_ENABLED", "Landroidx/datastore/preferences/core/Preferences$Key;", "", "getAUTO_REFRESH_ENABLED", "()Landroidx/datastore/preferences/core/Preferences$Key;", "FAVORITE_ROUTES", "", "", "getFAVORITE_ROUTES", "HAPTIC_FEEDBACK_ENABLED", "getHAPTIC_FEEDBACK_ENABLED", "LAST_FROM_STATION", "getLAST_FROM_STATION", "LAST_REFRESH_TIME", "", "getLAST_REFRESH_TIME", "LAST_TO_STATION", "getLAST_TO_STATION", "NOTIFICATION_ENABLED", "getNOTIFICATION_ENABLED", "THEME_MODE", "getTHEME_MODE", "app_release"})
    static final class PreferencesKeys {
        @org.jetbrains.annotations.NotNull()
        private static final androidx.datastore.preferences.core.Preferences.Key<java.lang.String> LAST_FROM_STATION = null;
        @org.jetbrains.annotations.NotNull()
        private static final androidx.datastore.preferences.core.Preferences.Key<java.lang.String> LAST_TO_STATION = null;
        @org.jetbrains.annotations.NotNull()
        private static final androidx.datastore.preferences.core.Preferences.Key<java.lang.Boolean> AUTO_REFRESH_ENABLED = null;
        @org.jetbrains.annotations.NotNull()
        private static final androidx.datastore.preferences.core.Preferences.Key<java.lang.Boolean> HAPTIC_FEEDBACK_ENABLED = null;
        @org.jetbrains.annotations.NotNull()
        private static final androidx.datastore.preferences.core.Preferences.Key<java.lang.String> THEME_MODE = null;
        @org.jetbrains.annotations.NotNull()
        private static final androidx.datastore.preferences.core.Preferences.Key<java.lang.Boolean> NOTIFICATION_ENABLED = null;
        @org.jetbrains.annotations.NotNull()
        private static final androidx.datastore.preferences.core.Preferences.Key<java.lang.Long> LAST_REFRESH_TIME = null;
        @org.jetbrains.annotations.NotNull()
        private static final androidx.datastore.preferences.core.Preferences.Key<java.util.Set<java.lang.String>> FAVORITE_ROUTES = null;
        @org.jetbrains.annotations.NotNull()
        public static final com.trackrat.android.data.preferences.UserPreferencesRepository.PreferencesKeys INSTANCE = null;
        
        private PreferencesKeys() {
            super();
        }
        
        @org.jetbrains.annotations.NotNull()
        public final androidx.datastore.preferences.core.Preferences.Key<java.lang.String> getLAST_FROM_STATION() {
            return null;
        }
        
        @org.jetbrains.annotations.NotNull()
        public final androidx.datastore.preferences.core.Preferences.Key<java.lang.String> getLAST_TO_STATION() {
            return null;
        }
        
        @org.jetbrains.annotations.NotNull()
        public final androidx.datastore.preferences.core.Preferences.Key<java.lang.Boolean> getAUTO_REFRESH_ENABLED() {
            return null;
        }
        
        @org.jetbrains.annotations.NotNull()
        public final androidx.datastore.preferences.core.Preferences.Key<java.lang.Boolean> getHAPTIC_FEEDBACK_ENABLED() {
            return null;
        }
        
        @org.jetbrains.annotations.NotNull()
        public final androidx.datastore.preferences.core.Preferences.Key<java.lang.String> getTHEME_MODE() {
            return null;
        }
        
        @org.jetbrains.annotations.NotNull()
        public final androidx.datastore.preferences.core.Preferences.Key<java.lang.Boolean> getNOTIFICATION_ENABLED() {
            return null;
        }
        
        @org.jetbrains.annotations.NotNull()
        public final androidx.datastore.preferences.core.Preferences.Key<java.lang.Long> getLAST_REFRESH_TIME() {
            return null;
        }
        
        @org.jetbrains.annotations.NotNull()
        public final androidx.datastore.preferences.core.Preferences.Key<java.util.Set<java.lang.String>> getFAVORITE_ROUTES() {
            return null;
        }
    }
    
    /**
     * Data class representing user preferences
     */
    @kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u00000\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0002\n\u0002\u0010\u000b\n\u0002\b\u0004\n\u0002\u0010\t\n\u0000\n\u0002\u0010\"\n\u0002\b\u0019\n\u0002\u0010\b\n\u0002\b\u0002\b\u0086\b\u0018\u00002\u00020\u0001B]\u0012\b\b\u0002\u0010\u0002\u001a\u00020\u0003\u0012\n\b\u0002\u0010\u0004\u001a\u0004\u0018\u00010\u0003\u0012\b\b\u0002\u0010\u0005\u001a\u00020\u0006\u0012\b\b\u0002\u0010\u0007\u001a\u00020\u0006\u0012\b\b\u0002\u0010\b\u001a\u00020\u0003\u0012\b\b\u0002\u0010\t\u001a\u00020\u0006\u0012\b\b\u0002\u0010\n\u001a\u00020\u000b\u0012\u000e\b\u0002\u0010\f\u001a\b\u0012\u0004\u0012\u00020\u00030\r\u00a2\u0006\u0002\u0010\u000eJ\t\u0010\u001b\u001a\u00020\u0003H\u00c6\u0003J\u000b\u0010\u001c\u001a\u0004\u0018\u00010\u0003H\u00c6\u0003J\t\u0010\u001d\u001a\u00020\u0006H\u00c6\u0003J\t\u0010\u001e\u001a\u00020\u0006H\u00c6\u0003J\t\u0010\u001f\u001a\u00020\u0003H\u00c6\u0003J\t\u0010 \u001a\u00020\u0006H\u00c6\u0003J\t\u0010!\u001a\u00020\u000bH\u00c6\u0003J\u000f\u0010\"\u001a\b\u0012\u0004\u0012\u00020\u00030\rH\u00c6\u0003Ja\u0010#\u001a\u00020\u00002\b\b\u0002\u0010\u0002\u001a\u00020\u00032\n\b\u0002\u0010\u0004\u001a\u0004\u0018\u00010\u00032\b\b\u0002\u0010\u0005\u001a\u00020\u00062\b\b\u0002\u0010\u0007\u001a\u00020\u00062\b\b\u0002\u0010\b\u001a\u00020\u00032\b\b\u0002\u0010\t\u001a\u00020\u00062\b\b\u0002\u0010\n\u001a\u00020\u000b2\u000e\b\u0002\u0010\f\u001a\b\u0012\u0004\u0012\u00020\u00030\rH\u00c6\u0001J\u0013\u0010$\u001a\u00020\u00062\b\u0010%\u001a\u0004\u0018\u00010\u0001H\u00d6\u0003J\t\u0010&\u001a\u00020\'H\u00d6\u0001J\t\u0010(\u001a\u00020\u0003H\u00d6\u0001R\u0011\u0010\u0005\u001a\u00020\u0006\u00a2\u0006\b\n\u0000\u001a\u0004\b\u000f\u0010\u0010R\u0017\u0010\f\u001a\b\u0012\u0004\u0012\u00020\u00030\r\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0011\u0010\u0012R\u0011\u0010\u0007\u001a\u00020\u0006\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0013\u0010\u0010R\u0011\u0010\u0002\u001a\u00020\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0014\u0010\u0015R\u0011\u0010\n\u001a\u00020\u000b\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0016\u0010\u0017R\u0013\u0010\u0004\u001a\u0004\u0018\u00010\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0018\u0010\u0015R\u0011\u0010\t\u001a\u00020\u0006\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0019\u0010\u0010R\u0011\u0010\b\u001a\u00020\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b\u001a\u0010\u0015\u00a8\u0006)"}, d2 = {"Lcom/trackrat/android/data/preferences/UserPreferencesRepository$UserPreferences;", "", "lastFromStation", "", "lastToStation", "autoRefreshEnabled", "", "hapticFeedbackEnabled", "themeMode", "notificationEnabled", "lastRefreshTime", "", "favoriteRoutes", "", "(Ljava/lang/String;Ljava/lang/String;ZZLjava/lang/String;ZJLjava/util/Set;)V", "getAutoRefreshEnabled", "()Z", "getFavoriteRoutes", "()Ljava/util/Set;", "getHapticFeedbackEnabled", "getLastFromStation", "()Ljava/lang/String;", "getLastRefreshTime", "()J", "getLastToStation", "getNotificationEnabled", "getThemeMode", "component1", "component2", "component3", "component4", "component5", "component6", "component7", "component8", "copy", "equals", "other", "hashCode", "", "toString", "app_release"})
    public static final class UserPreferences {
        @org.jetbrains.annotations.NotNull()
        private final java.lang.String lastFromStation = null;
        @org.jetbrains.annotations.Nullable()
        private final java.lang.String lastToStation = null;
        private final boolean autoRefreshEnabled = false;
        private final boolean hapticFeedbackEnabled = false;
        @org.jetbrains.annotations.NotNull()
        private final java.lang.String themeMode = null;
        private final boolean notificationEnabled = false;
        private final long lastRefreshTime = 0L;
        @org.jetbrains.annotations.NotNull()
        private final java.util.Set<java.lang.String> favoriteRoutes = null;
        
        public UserPreferences(@org.jetbrains.annotations.NotNull()
        java.lang.String lastFromStation, @org.jetbrains.annotations.Nullable()
        java.lang.String lastToStation, boolean autoRefreshEnabled, boolean hapticFeedbackEnabled, @org.jetbrains.annotations.NotNull()
        java.lang.String themeMode, boolean notificationEnabled, long lastRefreshTime, @org.jetbrains.annotations.NotNull()
        java.util.Set<java.lang.String> favoriteRoutes) {
            super();
        }
        
        @org.jetbrains.annotations.NotNull()
        public final java.lang.String getLastFromStation() {
            return null;
        }
        
        @org.jetbrains.annotations.Nullable()
        public final java.lang.String getLastToStation() {
            return null;
        }
        
        public final boolean getAutoRefreshEnabled() {
            return false;
        }
        
        public final boolean getHapticFeedbackEnabled() {
            return false;
        }
        
        @org.jetbrains.annotations.NotNull()
        public final java.lang.String getThemeMode() {
            return null;
        }
        
        public final boolean getNotificationEnabled() {
            return false;
        }
        
        public final long getLastRefreshTime() {
            return 0L;
        }
        
        @org.jetbrains.annotations.NotNull()
        public final java.util.Set<java.lang.String> getFavoriteRoutes() {
            return null;
        }
        
        public UserPreferences() {
            super();
        }
        
        @org.jetbrains.annotations.NotNull()
        public final java.lang.String component1() {
            return null;
        }
        
        @org.jetbrains.annotations.Nullable()
        public final java.lang.String component2() {
            return null;
        }
        
        public final boolean component3() {
            return false;
        }
        
        public final boolean component4() {
            return false;
        }
        
        @org.jetbrains.annotations.NotNull()
        public final java.lang.String component5() {
            return null;
        }
        
        public final boolean component6() {
            return false;
        }
        
        public final long component7() {
            return 0L;
        }
        
        @org.jetbrains.annotations.NotNull()
        public final java.util.Set<java.lang.String> component8() {
            return null;
        }
        
        @org.jetbrains.annotations.NotNull()
        public final com.trackrat.android.data.preferences.UserPreferencesRepository.UserPreferences copy(@org.jetbrains.annotations.NotNull()
        java.lang.String lastFromStation, @org.jetbrains.annotations.Nullable()
        java.lang.String lastToStation, boolean autoRefreshEnabled, boolean hapticFeedbackEnabled, @org.jetbrains.annotations.NotNull()
        java.lang.String themeMode, boolean notificationEnabled, long lastRefreshTime, @org.jetbrains.annotations.NotNull()
        java.util.Set<java.lang.String> favoriteRoutes) {
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