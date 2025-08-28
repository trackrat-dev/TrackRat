package com.trackrat.android.data.repository;

import com.trackrat.android.data.api.TrackRatApiService;
import dagger.internal.DaggerGenerated;
import dagger.internal.Factory;
import dagger.internal.QualifierMetadata;
import dagger.internal.ScopeMetadata;
import javax.annotation.processing.Generated;
import javax.inject.Provider;

@ScopeMetadata("javax.inject.Singleton")
@QualifierMetadata
@DaggerGenerated
@Generated(
    value = "dagger.internal.codegen.ComponentProcessor",
    comments = "https://dagger.dev"
)
@SuppressWarnings({
    "unchecked",
    "rawtypes",
    "KotlinInternal",
    "KotlinInternalInJava",
    "cast"
})
public final class TrackRatRepository_Factory implements Factory<TrackRatRepository> {
  private final Provider<TrackRatApiService> apiServiceProvider;

  public TrackRatRepository_Factory(Provider<TrackRatApiService> apiServiceProvider) {
    this.apiServiceProvider = apiServiceProvider;
  }

  @Override
  public TrackRatRepository get() {
    return newInstance(apiServiceProvider.get());
  }

  public static TrackRatRepository_Factory create(Provider<TrackRatApiService> apiServiceProvider) {
    return new TrackRatRepository_Factory(apiServiceProvider);
  }

  public static TrackRatRepository newInstance(TrackRatApiService apiService) {
    return new TrackRatRepository(apiService);
  }
}
