# Freemium Train System & Route Alert Limits — Implementation Design

## Summary

Gate free users to **1 train system** and **1 route alert (1 direction)**. Pro users get unlimited. Leverage the existing paywall infrastructure (SubscriptionService, PaywallView, StoreKit config with 1-week free trial). All changes are iOS-only. No backend changes.

---

## Free vs Pro

| Feature | Free | Pro |
|---------|------|-----|
| Train systems | 1 | Unlimited |
| Route alerts | 1 subscription, 1 direction | Unlimited |
| Departures, Live Activities, predictions, congestion | Full access | Full access |

---

## Architecture: 4 files changed, 0 files created

### 1. `SubscriptionService.swift` — Extend existing enums

**PremiumFeature** — add two cases:
```swift
enum PremiumFeature: String, CaseIterable {
    case developerChat = "Chat with Developer"
    case multipleTrainSystems = "Multiple Train Systems"
    case unlimitedAlerts = "Unlimited Route Alerts"
}
```

**PaywallContext** — add two cases with context-specific copy:
```swift
enum PaywallContext {
    case developerChat
    case trainSystems
    case routeAlerts
    case generic

    var subtext: String {
        switch self {
        case .trainSystems:
            return "Free users can follow one train system. Upgrade to Pro to track all 7 systems — start with a free 1-week trial."
        case .routeAlerts:
            return "Free users get one route alert. Upgrade to Pro for unlimited alerts across all your routes — start with a free 1-week trial."
        case .developerChat:
            return "Chat directly with the developer to request features or report issues."
        case .generic:
            return "Unlock the full TrackRat experience — start with a free 1-week trial."
        }
    }
}
```

**Limit constants** — add to SubscriptionService:
```swift
static let freeTrainSystemLimit = 1
static let freeRouteAlertLimit = 1
static let freeDirectionLimit = 1
```

**`hasAccess(to:)` stays flat** — it still just checks `isPro`. The limit enforcement happens in the UI, not in the access check. This keeps the service simple.

### 2. `PaywallView.swift` — Use context for messaging

The `context` property is already passed in but never rendered. Add a context-specific line below the developer letter when context is not `.generic` or `.developerChat`:

```swift
// After the letter/signature section, before pricing:
if let contextMessage = contextMessage {
    Text(contextMessage)
        .font(.subheadline)
        .foregroundColor(.orange.opacity(0.9))
        .padding(.horizontal, 24)
}
```

Where `contextMessage` returns `context.subtext` for `.trainSystems` and `.routeAlerts`, nil for `.developerChat` and `.generic` (since the letter already covers the general pitch).

Also update the success overlay text from "Head to Settings to chat with me anytime" to a generic "You now have full access to all TrackRat features" — since Pro now unlocks more than just chat.

### 3. `SettingsView.swift` — Gate train systems and route alerts

**Train system gating (in the ForEach for system rows):**

When a free user taps a system that isn't their currently selected one, and they already have 1 system selected:
```swift
// In the TrainSystemRow tap handler (line ~268-271):
Button {
    let isCurrentlySelected = appState.isSystemSelected(system)
    if !isCurrentlySelected
        && !subscriptionService.isPro
        && appState.selectedSystems.count >= SubscriptionService.freeTrainSystemLimit {
        paywallContext = .trainSystems
        showingPaywall = true
    } else {
        appState.toggleSystem(system)
    }
    UIImpactFeedbackGenerator(style: .light).impactOccurred()
}
```

Show a small "PRO" badge on non-selected systems for free users — reuse the same orange capsule pattern from the developer chat row:
```swift
// In TrainSystemRow, after the system name:
if !subscriptionService.isPro && !isSelected {
    Text("PRO")
        .font(.caption2.bold())
        .foregroundColor(.white)
        .padding(.horizontal, 6)
        .padding(.vertical, 2)
        .background(Capsule().fill(.orange))
}
```

Deselecting a system is always allowed (unless it's the last one — existing guard handles that).

**Route alert gating (at the "Add Route Alert" button, line ~358-361):**

```swift
Button {
    if !subscriptionService.isPro
        && alertService.subscriptions.count >= SubscriptionService.freeRouteAlertLimit {
        paywallContext = .routeAlerts
        showingPaywall = true
    } else {
        showAddRouteAlert = true
    }
    UIImpactFeedbackGenerator(style: .light).impactOccurred()
}
```

### 4. `AlertConfigurationSection.swift` — Gate second direction

In `DirectionalAlertConfigurationSheet`, for free users with no existing alert subscriptions, only the first direction is configurable. The second direction shows a Pro upsell instead of the configuration section:

```swift
// In the ForEach over directions (line ~84-93):
ForEach(0..<directions.count, id: \.self) { i in
    if directions[i].alreadySubscribed {
        alreadySubscribedBanner(label: directions[i].label)
    } else if i > 0 && !subscriptionService.isPro {
        proLockedDirectionBanner(label: directions[i].label)
    } else {
        AlertConfigurationSection(
            subscription: $directions[i].subscription,
            headerText: directions[i].label
        )
    }
}
```

The `proLockedDirectionBanner` shows:
```
[Direction label]
[lock.fill] PRO — Upgrade to add both directions
```

Styled like the existing `alreadySubscribedBanner` but with orange/lock instead of green/checkmark. Tapping it shows the paywall.

The Save button logic already filters by `activeDays != 0`, so the locked direction simply won't produce a subscription.

### 5. `OnboardingView.swift` — Cap system selection at 1 for free users

In `systemSelectionView()`, when a free user taps a system and already has 1 selected:
```swift
// In the SystemSelectionCard tap handler:
if !subscriptionService.isPro
    && appState.selectedSystems.count >= SubscriptionService.freeTrainSystemLimit
    && !appState.isSystemSelected(system) {
    paywallContext = .trainSystems
    showingPaywall = true
} else {
    appState.toggleSystem(system, allowEmpty: true)
}
```

Add a `.sheet(isPresented: $showingPaywall)` to the onboarding view for the paywall.

Show the same "PRO" badge on non-selected systems.

---

## Existing Users Migration

**No forced migration.** Existing selections persist. The limits only apply when trying to ADD:
- User with 3 systems? They keep all 3. But they can't add a 4th (or re-add one they remove).
- User with 5 alerts? They keep all 5. But they can't add a 6th.

This is the gentlest approach — no one loses functionality they already have. Over time, if they remove a system, they can't add a second one back without Pro.

**Rationale:** Forcing existing users to downgrade would create immediate negative sentiment. The "keep what you have, gate new additions" pattern is standard (Spotify, Notion, etc.).

---

## UX Flow Examples

### Free user opens app for first time
1. Onboarding → system selection → picks NJT
2. Taps PATH → paywall appears: "Free users can follow one train system. Upgrade to Pro to track all 7 — start with a free 1-week trial."
3. User can dismiss paywall and continue with NJT, or start trial

### Free user tries to add route alert
1. Settings → Route Alerts → Edit → Add Route Alert
2. Already has 1 alert → paywall: "Free users get one route alert. Upgrade to Pro for unlimited alerts — start with a free 1-week trial."
3. User can dismiss and keep their existing alert, or start trial

### Free user creates first route alert (line mode)
1. Selects NJT → Northeast Corridor → direction config sheet
2. "To New York Penn" direction: full config section (active)
3. "To Trenton" direction: locked banner with PRO badge and lock icon
4. User configures the one free direction and saves

### Free user starts trial
1. Taps "Start Free Trial" on any paywall
2. All limits removed immediately (isPro = true)
3. Success overlay: "You now have full access to all TrackRat features"
4. 7 days of full access, then $2.99/mo or features re-gate

---

## What This Design Does NOT Do

1. **No backend changes** — client-side enforcement only. Backend accepts whatever the client sends. Server-side validation can be added later.
2. **No new files** — all changes go into existing files.
3. **No departure/search gating** — users can still search departures for their selected system. We don't block viewing trains; we block adding more systems.
4. **No web changes** — web stays fully free for now.
5. **No changes to the paywall letter content** — Andy's letter is system-agnostic and works well. We just add a context line below it.
6. **No changes to alert evaluation or push notifications** — existing alerts continue to work regardless of subscription status.

---

## Files Changed (5 total)

| File | Changes |
|------|---------|
| `ios/TrackRat/Services/SubscriptionService.swift` | Add 2 PremiumFeature cases, 2 PaywallContext cases with copy, 3 limit constants |
| `ios/TrackRat/Views/Paywall/PaywallView.swift` | Render context subtext, update success overlay text |
| `ios/TrackRat/Views/Screens/SettingsView.swift` | Gate system toggle + alert add button, add PRO badges |
| `ios/TrackRat/Views/Components/AlertConfigurationSection.swift` | Gate second direction in DirectionalAlertConfigurationSheet |
| `ios/TrackRat/Views/Screens/OnboardingView.swift` | Cap system selection at 1, add paywall sheet |

---

## Testing

Unit tests for:
- `SubscriptionService` limit constants exist and are correct
- `PaywallContext` subtext returns non-empty strings for all cases
- Free user cannot exceed system limit (mock isPro = false)
- Pro user has no limits (mock isPro = true)
- Existing selections beyond limit are preserved (not removed)

Manual testing:
- Onboarding: verify only 1 system selectable, PRO badges visible, paywall dismissible
- Settings: verify system toggle gated, alert add button gated, PRO badges visible
- Direction sheet: verify second direction locked, first direction configurable
- Purchase flow: verify all limits removed after trial/purchase
- Existing user: verify no data loss on upgrade
