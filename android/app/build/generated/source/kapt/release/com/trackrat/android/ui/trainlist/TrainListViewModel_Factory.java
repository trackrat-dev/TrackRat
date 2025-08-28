package com.trackrat.android.ui.trainlist;

import com.trackrat.android.data.preferences.UserPreferencesRepository;
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
public final class TrainListViewModel_Factory implements Factory<TrainListViewModel> {
  private final Provider<TrackRatRepository> repositoryProvider;

  private final Provider<UserPreferencesRepository> preferencesRepositoryProvider;

  public TrainListViewModel_Factory(Provider<TrackRatRepository> repositoryProvider,
      Provider<UserPreferencesRepository> preferencesRepositoryProvider) {
    this.repositoryProvider = repositoryProvider;
    this.preferencesRepositoryProvider = preferencesRepositoryProvider;
  }

  @Override
  public TrainListViewModel get() {
    return newInstance(repositoryProvider.get(), preferencesRepositoryProvider.get());
  }

  public static TrainListViewModel_Factory create(Provider<TrackRatRepository> repositoryProvider,
      Provider<UserPreferencesRepository> preferencesRepositoryProvider) {
    return new TrainListViewModel_Factory(repositoryProvider, preferencesRepositoryProvider);
  }

  public static TrainListViewModel newInstance(TrackRatRepository repository,
      UserPreferencesRepository preferencesRepository) {
    return new TrainListViewModel(repository, preferencesRepository);
  }
}
