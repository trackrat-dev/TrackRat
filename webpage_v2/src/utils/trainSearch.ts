import { TransitSystem } from '../types';

const TRAIN_SEARCH_SYSTEMS: TransitSystem[] = ['NJT', 'AMTRAK', 'LIRR', 'MNR'];

const TRAIN_PREFIX_BY_SYSTEM: Partial<Record<TransitSystem, string>> = {
  AMTRAK: 'A',
  LIRR: 'L',
  MNR: 'M',
};

const TRAIN_SYSTEM_BY_PREFIX: Record<string, TransitSystem> = {
  A: 'AMTRAK',
  L: 'LIRR',
  M: 'MNR',
};

export function getTrainSearchCandidates(
  input: string,
  preferredSystems: TransitSystem[] = []
): string[] {
  const trimmed = input.trim().toUpperCase();
  if (!trimmed) return [];

  const explicitPrefix = trimmed.charAt(0);
  const prefixedRemainder = trimmed.slice(1);
  if (
    explicitPrefix in TRAIN_SYSTEM_BY_PREFIX &&
    trimmed.length >= 3 &&
    /^\d+$/.test(prefixedRemainder)
  ) {
    return [trimmed];
  }

  if (!/^\d{2,}$/.test(trimmed)) {
    return [];
  }

  const activeSystems = preferredSystems.filter((system) =>
    TRAIN_SEARCH_SYSTEMS.includes(system)
  );
  const systemsToSearch = activeSystems.length > 0 ? activeSystems : TRAIN_SEARCH_SYSTEMS;

  return systemsToSearch.map((system) => {
    const prefix = TRAIN_PREFIX_BY_SYSTEM[system];
    return prefix ? `${prefix}${trimmed}` : trimmed;
  });
}

export function inferTrainSearchSystem(trainNumber: string): TransitSystem | undefined {
  const trimmed = trainNumber.trim().toUpperCase();
  const prefix = trimmed.charAt(0);

  if (prefix in TRAIN_SYSTEM_BY_PREFIX) {
    return TRAIN_SYSTEM_BY_PREFIX[prefix];
  }

  if (/^\d{2,}$/.test(trimmed)) {
    return 'NJT';
  }

  return undefined;
}
