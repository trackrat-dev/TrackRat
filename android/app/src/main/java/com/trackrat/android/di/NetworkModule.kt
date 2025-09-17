package com.trackrat.android.di

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import com.trackrat.android.data.api.HtmlEntityDecodeJsonAdapterFactory
import com.trackrat.android.data.api.TrackRatApiService
import com.trackrat.android.data.api.ZonedDateTimeAdapter
import com.trackrat.android.data.preferences.EnvironmentManager
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import kotlinx.coroutines.runBlocking
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    @Provides
    @Singleton
    fun provideMoshi(): Moshi {
        return Moshi.Builder()
            .add(ZonedDateTimeAdapter())  // Custom datetime adapter for Eastern Time
            .add(HtmlEntityDecodeJsonAdapterFactory())  // Decode HTML entities like &#9992;
            .add(KotlinJsonAdapterFactory())  // Must be last
            .build()
    }

    @Provides
    @Singleton
    fun provideOkHttpClient(): OkHttpClient {
        // Add logging for debug builds
        val loggingInterceptor = HttpLoggingInterceptor().apply {
            // Use BODY for debug logging (can be configured later)
            level = HttpLoggingInterceptor.Level.BODY
        }
        
        return OkHttpClient.Builder()
            .addInterceptor(loggingInterceptor)
            .connectTimeout(30, java.util.concurrent.TimeUnit.SECONDS)
            .readTimeout(30, java.util.concurrent.TimeUnit.SECONDS)
            .build()
    }

    @Provides
    @Singleton
    fun provideRetrofit(
        okHttpClient: OkHttpClient, 
        moshi: Moshi,
        environmentManager: EnvironmentManager
    ): Retrofit {
        // Get the configured base URL from EnvironmentManager
        // This allows switching between environments in debug builds
        val baseUrl = runBlocking { 
            environmentManager.loadServerEnvironment().baseURL 
        }
        
        return Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(okHttpClient)
            .addConverterFactory(MoshiConverterFactory.create(moshi))
            .build()
    }

    @Provides
    @Singleton
    fun provideTrackRatApiService(retrofit: Retrofit): TrackRatApiService {
        return retrofit.create(TrackRatApiService::class.java)
    }
}