package com.trackrat.android.services;

import com.trackrat.android.data.repository.TrackRatRepository;
import dagger.MembersInjector;
import dagger.internal.DaggerGenerated;
import dagger.internal.InjectedFieldSignature;
import dagger.internal.QualifierMetadata;
import javax.annotation.processing.Generated;
import javax.inject.Provider;

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
public final class TrainTrackingService_MembersInjector implements MembersInjector<TrainTrackingService> {
  private final Provider<TrackRatRepository> repositoryProvider;

  public TrainTrackingService_MembersInjector(Provider<TrackRatRepository> repositoryProvider) {
    this.repositoryProvider = repositoryProvider;
  }

  public static MembersInjector<TrainTrackingService> create(
      Provider<TrackRatRepository> repositoryProvider) {
    return new TrainTrackingService_MembersInjector(repositoryProvider);
  }

  @Override
  public void injectMembers(TrainTrackingService instance) {
    injectRepository(instance, repositoryProvider.get());
  }

  @InjectedFieldSignature("com.trackrat.android.services.TrainTrackingService.repository")
  public static void injectRepository(TrainTrackingService instance,
      TrackRatRepository repository) {
    instance.repository = repository;
  }
}
