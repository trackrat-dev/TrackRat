package com.trackrat.android.ui.stationselection;

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
public final class StationSelectionViewModel_Factory implements Factory<StationSelectionViewModel> {
  private final Provider<TrackRatRepository> repositoryProvider;

  public StationSelectionViewModel_Factory(Provider<TrackRatRepository> repositoryProvider) {
    this.repositoryProvider = repositoryProvider;
  }

  @Override
  public StationSelectionViewModel get() {
    return newInstance(repositoryProvider.get());
  }

  public static StationSelectionViewModel_Factory create(
      Provider<TrackRatRepository> repositoryProvider) {
    return new StationSelectionViewModel_Factory(repositoryProvider);
  }

  public static StationSelectionViewModel newInstance(TrackRatRepository repository) {
    return new StationSelectionViewModel(repository);
  }
}
