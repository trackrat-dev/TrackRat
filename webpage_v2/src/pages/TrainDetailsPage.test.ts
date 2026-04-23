import { describe, it, expect } from 'vitest';

/**
 * Tests the shouldShowPredictions logic from TrainDetailsPage.
 * The actual condition in the component is:
 *   stationSupported && !predictionStop?.track && !predictionStop?.has_departed_station && !train.is_cancelled
 */
function shouldShowPredictions(
  stationSupported: boolean,
  predictionStop: { track?: string | null; has_departed_station: boolean } | undefined,
  isCancelled: boolean,
): boolean {
  return (
    stationSupported &&
    !predictionStop?.track &&
    !predictionStop?.has_departed_station &&
    !isCancelled
  );
}

describe('shouldShowPredictions', () => {
  it('shows predictions when station is supported, no track assigned, not departed, not cancelled', () => {
    expect(shouldShowPredictions(true, { has_departed_station: false }, false)).toBe(true);
  });

  it('hides predictions when station is not supported', () => {
    expect(shouldShowPredictions(false, { has_departed_station: false }, false)).toBe(false);
  });

  it('hides predictions when track is already assigned', () => {
    expect(shouldShowPredictions(true, { track: '5', has_departed_station: false }, false)).toBe(false);
  });

  it('hides predictions when train has departed the origin station', () => {
    expect(shouldShowPredictions(true, { has_departed_station: true }, false)).toBe(false);
  });

  it('hides predictions when train is cancelled', () => {
    expect(shouldShowPredictions(true, { has_departed_station: false }, true)).toBe(false);
  });

  it('does not crash when predictionStop is undefined (station not found in stops)', () => {
    // When predictionStop is undefined, optional chaining returns undefined,
    // and !undefined is true — so only stationSupported gates visibility.
    // In practice, stationSupported would be false if the station isn't in the stops list.
    expect(shouldShowPredictions(true, undefined, false)).toBe(true);
    expect(shouldShowPredictions(false, undefined, false)).toBe(false);
  });

  it('hides predictions when departed AND track assigned (multiple disqualifiers)', () => {
    expect(shouldShowPredictions(true, { track: '3', has_departed_station: true }, false)).toBe(false);
  });
});
