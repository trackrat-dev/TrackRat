package com.trackrat.android.ui.traindetail;

import android.app.Application;
import com.trackrat.android.data.repository.TrackRatRepository;
import dagger.internal.DaggerGenerated;
import dagger.internal.Factory;
import dagger.internal.QualifierMetadata;
import dagger.internal.ScopeMetadata;
import javax.annotation.processing.Generated;
import javax.inject.Provider;

@ScopeMetadata
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
public final class TrainDetailViewModel_Factory implements Factory<TrainDetailViewModel> {
  private final Provider<Application> applicationProvider;

  private final Provider<TrackRatRepository> repositoryProvider;

  public TrainDetailViewModel_Factory(Provider<Application> applicationProvider,
      Provider<TrackRatRepository> repositoryProvider) {
    this.applicationProvider = applicationProvider;
    this.repositoryProvider = repositoryProvider;
  }

  @Override
  public TrainDetailViewModel get() {
    return newInstance(applicationProvider.get(), repositoryProvider.get());
  }

  public static TrainDetailViewModel_Factory create(Provider<Application> applicationProvider,
      Provider<TrackRatRepository> repositoryProvider) {
    return new TrainDetailViewModel_Factory(applicationProvider, repositoryProvider);
  }

  public static TrainDetailViewModel newInstance(Application application,
      TrackRatRepository repository) {
    return new TrainDetailViewModel(application, repository);
  }
}
