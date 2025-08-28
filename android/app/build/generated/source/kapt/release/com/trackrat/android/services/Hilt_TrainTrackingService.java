package com.trackrat.android.services;

import android.app.Service;
import androidx.annotation.CallSuper;
import dagger.hilt.android.internal.managers.ServiceComponentManager;
import dagger.hilt.internal.GeneratedComponentManagerHolder;
import dagger.hilt.internal.UnsafeCasts;
import java.lang.Object;
import java.lang.Override;
import javax.annotation.processing.Generated;

/**
 * A generated base class to be extended by the @dagger.hilt.android.AndroidEntryPoint annotated class. If using the Gradle plugin, this is swapped as the base class via bytecode transformation.
 */
@Generated("dagger.hilt.android.processor.internal.androidentrypoint.ServiceGenerator")
public abstract class Hilt_TrainTrackingService extends Service implements GeneratedComponentManagerHolder {
  private volatile ServiceComponentManager componentManager;

  private final Object componentManagerLock = new Object();

  private boolean injected = false;

  Hilt_TrainTrackingService() {
    super();
  }

  @CallSuper
  @Override
  public void onCreate() {
    inject();
    super.onCreate();
  }

  protected ServiceComponentManager createComponentManager() {
    return new ServiceComponentManager(this);
  }

  @Override
  public final ServiceComponentManager componentManager() {
    if (componentManager == null) {
      synchronized (componentManagerLock) {
        if (componentManager == null) {
          componentManager = createComponentManager();
        }
      }
    }
    return componentManager;
  }

  protected void inject() {
    if (!injected) {
      injected = true;
      ((TrainTrackingService_GeneratedInjector) this.generatedComponent()).injectTrainTrackingService(UnsafeCasts.<TrainTrackingService>unsafeCast(this));
    }
  }

  @Override
  public final Object generatedComponent() {
    return this.componentManager().generatedComponent();
  }
}
