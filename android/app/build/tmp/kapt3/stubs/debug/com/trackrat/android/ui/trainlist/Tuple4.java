package com.trackrat.android.ui.trainlist;

import androidx.compose.foundation.layout.*;
import androidx.compose.material.icons.Icons;
import androidx.compose.material3.*;
import androidx.compose.runtime.*;
import androidx.compose.ui.Alignment;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.hapticfeedback.HapticFeedbackType;
import androidx.compose.ui.text.font.FontWeight;
import androidx.compose.ui.text.style.TextOverflow;
import androidx.compose.ui.tooling.preview.Preview;
import com.trackrat.android.data.models.TrainV2;
import com.trackrat.android.utils.Constants;
import com.trackrat.android.utils.HapticFeedbackHelper;
import java.time.format.DateTimeFormatter;

@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000$\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0010\u0000\n\u0002\b\u0012\n\u0002\u0010\u000b\n\u0002\b\u0002\n\u0002\u0010\b\n\u0000\n\u0002\u0010\u000e\n\u0000\b\u0086\b\u0018\u0000*\u0004\b\u0000\u0010\u0001*\u0004\b\u0001\u0010\u0002*\u0004\b\u0002\u0010\u0003*\u0004\b\u0003\u0010\u00042\u00020\u0005B%\u0012\u0006\u0010\u0006\u001a\u00028\u0000\u0012\u0006\u0010\u0007\u001a\u00028\u0001\u0012\u0006\u0010\b\u001a\u00028\u0002\u0012\u0006\u0010\t\u001a\u00028\u0003\u00a2\u0006\u0002\u0010\nJ\u000e\u0010\u0011\u001a\u00028\u0000H\u00c6\u0003\u00a2\u0006\u0002\u0010\fJ\u000e\u0010\u0012\u001a\u00028\u0001H\u00c6\u0003\u00a2\u0006\u0002\u0010\fJ\u000e\u0010\u0013\u001a\u00028\u0002H\u00c6\u0003\u00a2\u0006\u0002\u0010\fJ\u000e\u0010\u0014\u001a\u00028\u0003H\u00c6\u0003\u00a2\u0006\u0002\u0010\fJN\u0010\u0015\u001a\u001a\u0012\u0004\u0012\u00028\u0000\u0012\u0004\u0012\u00028\u0001\u0012\u0004\u0012\u00028\u0002\u0012\u0004\u0012\u00028\u00030\u00002\b\b\u0002\u0010\u0006\u001a\u00028\u00002\b\b\u0002\u0010\u0007\u001a\u00028\u00012\b\b\u0002\u0010\b\u001a\u00028\u00022\b\b\u0002\u0010\t\u001a\u00028\u0003H\u00c6\u0001\u00a2\u0006\u0002\u0010\u0016J\u0013\u0010\u0017\u001a\u00020\u00182\b\u0010\u0019\u001a\u0004\u0018\u00010\u0005H\u00d6\u0003J\t\u0010\u001a\u001a\u00020\u001bH\u00d6\u0001J\t\u0010\u001c\u001a\u00020\u001dH\u00d6\u0001R\u0013\u0010\u0006\u001a\u00028\u0000\u00a2\u0006\n\n\u0002\u0010\r\u001a\u0004\b\u000b\u0010\fR\u0013\u0010\t\u001a\u00028\u0003\u00a2\u0006\n\n\u0002\u0010\r\u001a\u0004\b\u000e\u0010\fR\u0013\u0010\u0007\u001a\u00028\u0001\u00a2\u0006\n\n\u0002\u0010\r\u001a\u0004\b\u000f\u0010\fR\u0013\u0010\b\u001a\u00028\u0002\u00a2\u0006\n\n\u0002\u0010\r\u001a\u0004\b\u0010\u0010\f\u00a8\u0006\u001e"}, d2 = {"Lcom/trackrat/android/ui/trainlist/Tuple4;", "A", "B", "C", "D", "", "first", "second", "third", "fourth", "(Ljava/lang/Object;Ljava/lang/Object;Ljava/lang/Object;Ljava/lang/Object;)V", "getFirst", "()Ljava/lang/Object;", "Ljava/lang/Object;", "getFourth", "getSecond", "getThird", "component1", "component2", "component3", "component4", "copy", "(Ljava/lang/Object;Ljava/lang/Object;Ljava/lang/Object;Ljava/lang/Object;)Lcom/trackrat/android/ui/trainlist/Tuple4;", "equals", "", "other", "hashCode", "", "toString", "", "app_debug"})
public final class Tuple4<A extends java.lang.Object, B extends java.lang.Object, C extends java.lang.Object, D extends java.lang.Object> {
    private final A first = null;
    private final B second = null;
    private final C third = null;
    private final D fourth = null;
    
    public Tuple4(A first, B second, C third, D fourth) {
        super();
    }
    
    public final A getFirst() {
        return null;
    }
    
    public final B getSecond() {
        return null;
    }
    
    public final C getThird() {
        return null;
    }
    
    public final D getFourth() {
        return null;
    }
    
    public final A component1() {
        return null;
    }
    
    public final B component2() {
        return null;
    }
    
    public final C component3() {
        return null;
    }
    
    public final D component4() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final com.trackrat.android.ui.trainlist.Tuple4<A, B, C, D> copy(A first, B second, C third, D fourth) {
        return null;
    }
    
    @java.lang.Override()
    public boolean equals(@org.jetbrains.annotations.Nullable()
    java.lang.Object other) {
        return false;
    }
    
    @java.lang.Override()
    public int hashCode() {
        return 0;
    }
    
    @java.lang.Override()
    @org.jetbrains.annotations.NotNull()
    public java.lang.String toString() {
        return null;
    }
}