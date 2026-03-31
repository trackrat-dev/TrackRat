package com.trackrat.android.di

import android.content.Context
import com.trackrat.android.data.preferences.UserPreferencesRepository
import com.trackrat.android.services.TrackingStateRepository
import com.trackrat.android.services.TrainTrackingNotificationManager
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun provideUserPreferencesRepository(
        @ApplicationContext context: Context
    ): UserPreferencesRepository {
        return UserPreferencesRepository(context)
    }

    @Provides
    @Singleton
    fun provideTrackingStateRepository(
        @ApplicationContext context: Context
    ): TrackingStateRepository {
        return TrackingStateRepository(context)
    }

    @Provides
    @Singleton
    fun provideTrainTrackingNotificationManager(
        @ApplicationContext context: Context
    ): TrainTrackingNotificationManager {
        return TrainTrackingNotificationManager(context)
    }
}