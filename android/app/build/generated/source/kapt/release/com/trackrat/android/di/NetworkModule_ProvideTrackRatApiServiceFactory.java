package com.trackrat.android.di;

import com.trackrat.android.data.api.TrackRatApiService;
import dagger.internal.DaggerGenerated;
import dagger.internal.Factory;
import dagger.internal.Preconditions;
import dagger.internal.QualifierMetadata;
import dagger.internal.ScopeMetadata;
import javax.annotation.processing.Generated;
import javax.inject.Provider;
import retrofit2.Retrofit;

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
public final class NetworkModule_ProvideTrackRatApiServiceFactory implements Factory<TrackRatApiService> {
  private final Provider<Retrofit> retrofitProvider;

  public NetworkModule_ProvideTrackRatApiServiceFactory(Provider<Retrofit> retrofitProvider) {
    this.retrofitProvider = retrofitProvider;
  }

  @Override
  public TrackRatApiService get() {
    return provideTrackRatApiService(retrofitProvider.get());
  }

  public static NetworkModule_ProvideTrackRatApiServiceFactory create(
      Provider<Retrofit> retrofitProvider) {
    return new NetworkModule_ProvideTrackRatApiServiceFactory(retrofitProvider);
  }

  public static TrackRatApiService provideTrackRatApiService(Retrofit retrofit) {
    return Preconditions.checkNotNullFromProvides(NetworkModule.INSTANCE.provideTrackRatApiService(retrofit));
  }
}
