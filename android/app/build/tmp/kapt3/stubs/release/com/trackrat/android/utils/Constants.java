package com.trackrat.android.utils;

/**
 * Application-wide constants to avoid magic numbers
 */
@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000\"\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0010\t\n\u0000\n\u0002\u0010\b\n\u0002\b\u0007\n\u0002\u0010\u000e\n\u0002\b\u0012\b\u00c6\u0002\u0018\u00002\u00020\u0001:\u0003\u001d\u001e\u001fB\u0007\b\u0002\u00a2\u0006\u0002\u0010\u0002R\u000e\u0010\u0003\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0005\u001a\u00020\u0006X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0007\u001a\u00020\u0006X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\b\u001a\u00020\u0006X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\t\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\n\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u000b\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\f\u001a\u00020\u0006X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\r\u001a\u00020\u000eX\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u000f\u001a\u00020\u000eX\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0010\u001a\u00020\u0006X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0011\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0012\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0013\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0014\u001a\u00020\u0006X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0015\u001a\u00020\u0006X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0016\u001a\u00020\u0006X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0017\u001a\u00020\u0006X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0018\u001a\u00020\u0006X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0019\u001a\u00020\u0006X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u001a\u001a\u00020\u0006X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u001b\u001a\u00020\u0006X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u001c\u001a\u00020\u000eX\u0086T\u00a2\u0006\u0002\n\u0000\u00a8\u0006 "}, d2 = {"Lcom/trackrat/android/utils/Constants;", "", "()V", "AUTO_REFRESH_INTERVAL_MS", "", "BORDER_RADIUS_LARGE_DP", "", "BORDER_RADIUS_MEDIUM_DP", "BORDER_RADIUS_SMALL_DP", "BRAND_ORANGE", "BRAND_ORANGE_DARK", "BRAND_ORANGE_LIGHT", "CARD_ELEVATION_DP", "DATETIME_FORMAT_ISO", "", "DATE_FORMAT_API", "DEFAULT_API_LIMIT", "HAPTIC_FEEDBACK_DURATION_MS", "INITIAL_RETRY_DELAY_MS", "LOADING_SKELETON_SHIMMER_DURATION_MS", "MAX_RETRY_ATTEMPTS", "MIN_TOUCH_TARGET_DP", "PADDING_LARGE_DP", "PADDING_MEDIUM_DP", "PADDING_SMALL_DP", "SEARCH_API_LIMIT", "SHIMMER_COUNT_TRAIN_DETAIL_STOPS", "SHIMMER_COUNT_TRAIN_LIST", "TIME_FORMAT_DISPLAY", "StationCodes", "StationNames", "TrainStatus", "app_release"})
public final class Constants {
    public static final int DEFAULT_API_LIMIT = 50;
    public static final int SEARCH_API_LIMIT = 100;
    public static final long AUTO_REFRESH_INTERVAL_MS = 30000L;
    public static final long LOADING_SKELETON_SHIMMER_DURATION_MS = 1000L;
    public static final long HAPTIC_FEEDBACK_DURATION_MS = 50L;
    public static final int MAX_RETRY_ATTEMPTS = 3;
    public static final long INITIAL_RETRY_DELAY_MS = 1000L;
    public static final int CARD_ELEVATION_DP = 4;
    public static final int BORDER_RADIUS_SMALL_DP = 4;
    public static final int BORDER_RADIUS_MEDIUM_DP = 8;
    public static final int BORDER_RADIUS_LARGE_DP = 12;
    public static final int PADDING_SMALL_DP = 8;
    public static final int PADDING_MEDIUM_DP = 16;
    public static final int PADDING_LARGE_DP = 24;
    public static final int MIN_TOUCH_TARGET_DP = 48;
    public static final long BRAND_ORANGE = 4294927872L;
    public static final long BRAND_ORANGE_LIGHT = 4294936627L;
    public static final long BRAND_ORANGE_DARK = 4291580416L;
    public static final int SHIMMER_COUNT_TRAIN_LIST = 8;
    public static final int SHIMMER_COUNT_TRAIN_DETAIL_STOPS = 12;
    @org.jetbrains.annotations.NotNull()
    public static final java.lang.String DATE_FORMAT_API = "yyyy-MM-dd";
    @org.jetbrains.annotations.NotNull()
    public static final java.lang.String TIME_FORMAT_DISPLAY = "h:mm a";
    @org.jetbrains.annotations.NotNull()
    public static final java.lang.String DATETIME_FORMAT_ISO = "yyyy-MM-dd\'T\'HH:mm:ss.SSSXXX";
    @org.jetbrains.annotations.NotNull()
    public static final com.trackrat.android.utils.Constants INSTANCE = null;
    
    private Constants() {
        super();
    }
    
    @kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000\u0014\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0010\u000e\n\u0002\b\u0005\b\u00c6\u0002\u0018\u00002\u00020\u0001B\u0007\b\u0002\u00a2\u0006\u0002\u0010\u0002R\u000e\u0010\u0003\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0005\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0006\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0007\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\b\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000\u00a8\u0006\t"}, d2 = {"Lcom/trackrat/android/utils/Constants$StationCodes;", "", "()V", "METROPARK", "", "NEWARK_PENN", "NEW_YORK_PENN", "PRINCETON_JUNCTION", "TRENTON", "app_release"})
    public static final class StationCodes {
        @org.jetbrains.annotations.NotNull()
        public static final java.lang.String NEW_YORK_PENN = "NY";
        @org.jetbrains.annotations.NotNull()
        public static final java.lang.String NEWARK_PENN = "NP";
        @org.jetbrains.annotations.NotNull()
        public static final java.lang.String TRENTON = "TR";
        @org.jetbrains.annotations.NotNull()
        public static final java.lang.String PRINCETON_JUNCTION = "PJ";
        @org.jetbrains.annotations.NotNull()
        public static final java.lang.String METROPARK = "MP";
        @org.jetbrains.annotations.NotNull()
        public static final com.trackrat.android.utils.Constants.StationCodes INSTANCE = null;
        
        private StationCodes() {
            super();
        }
    }
    
    @kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000\u0014\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0010\u000e\n\u0002\b\u0005\b\u00c6\u0002\u0018\u00002\u00020\u0001B\u0007\b\u0002\u00a2\u0006\u0002\u0010\u0002R\u000e\u0010\u0003\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0005\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0006\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0007\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\b\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000\u00a8\u0006\t"}, d2 = {"Lcom/trackrat/android/utils/Constants$StationNames;", "", "()V", "METROPARK", "", "NEWARK_PENN", "NEW_YORK_PENN", "PRINCETON_JUNCTION", "TRENTON", "app_release"})
    public static final class StationNames {
        @org.jetbrains.annotations.NotNull()
        public static final java.lang.String NEW_YORK_PENN = "New York Penn";
        @org.jetbrains.annotations.NotNull()
        public static final java.lang.String NEWARK_PENN = "Newark Penn";
        @org.jetbrains.annotations.NotNull()
        public static final java.lang.String TRENTON = "Trenton";
        @org.jetbrains.annotations.NotNull()
        public static final java.lang.String PRINCETON_JUNCTION = "Princeton Junction";
        @org.jetbrains.annotations.NotNull()
        public static final java.lang.String METROPARK = "Metropark";
        @org.jetbrains.annotations.NotNull()
        public static final com.trackrat.android.utils.Constants.StationNames INSTANCE = null;
        
        private StationNames() {
            super();
        }
    }
    
    @kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000\u0014\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0010\u000e\n\u0002\b\u0006\b\u00c6\u0002\u0018\u00002\u00020\u0001B\u0007\b\u0002\u00a2\u0006\u0002\u0010\u0002R\u000e\u0010\u0003\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0005\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0006\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0007\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\b\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\t\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000\u00a8\u0006\n"}, d2 = {"Lcom/trackrat/android/utils/Constants$TrainStatus;", "", "()V", "ALL_ABOARD", "", "BOARDING", "CANCELLED", "DELAYED", "DEPARTED", "ON_TIME", "app_release"})
    public static final class TrainStatus {
        @org.jetbrains.annotations.NotNull()
        public static final java.lang.String BOARDING = "BOARDING";
        @org.jetbrains.annotations.NotNull()
        public static final java.lang.String ALL_ABOARD = "ALL ABOARD";
        @org.jetbrains.annotations.NotNull()
        public static final java.lang.String DEPARTED = "DEPARTED";
        @org.jetbrains.annotations.NotNull()
        public static final java.lang.String DELAYED = "DELAYED";
        @org.jetbrains.annotations.NotNull()
        public static final java.lang.String CANCELLED = "CANCELLED";
        @org.jetbrains.annotations.NotNull()
        public static final java.lang.String ON_TIME = "ON TIME";
        @org.jetbrains.annotations.NotNull()
        public static final com.trackrat.android.utils.Constants.TrainStatus INSTANCE = null;
        
        private TrainStatus() {
            super();
        }
    }
}