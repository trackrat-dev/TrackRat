import { describe, it, expect, vi, beforeEach } from 'vitest';
import { isShareSupported, share, buildTrainShareData } from './share';

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('isShareSupported', () => {
  it('returns true when navigator.share exists', () => {
    vi.stubGlobal('navigator', { share: vi.fn() });
    expect(isShareSupported()).toBe(true);
  });

  it('returns false when navigator.share is missing', () => {
    vi.stubGlobal('navigator', {});
    expect(isShareSupported()).toBe(false);
  });
});

describe('share', () => {
  const data = { title: 'Test', text: 'Body', url: 'https://example.com' };

  it('uses Web Share API when supported', async () => {
    const shareFn = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', { share: shareFn });

    const result = await share(data);

    expect(shareFn).toHaveBeenCalledWith({
      title: 'Test',
      text: 'Body',
      url: 'https://example.com',
    });
    expect(result).toBe(true);
  });

  it('falls back to clipboard when Web Share not supported', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', { clipboard: { writeText } });

    const result = await share(data);

    expect(writeText).toHaveBeenCalledWith('https://example.com');
    expect(result).toBe(true);
  });

  it('returns false when user cancels share (AbortError)', async () => {
    const abortError = new Error('User cancelled');
    abortError.name = 'AbortError';
    vi.stubGlobal('navigator', { share: vi.fn().mockRejectedValue(abortError) });

    const result = await share(data);
    expect(result).toBe(false);
  });

  it('returns false on other share errors', async () => {
    vi.stubGlobal('navigator', { share: vi.fn().mockRejectedValue(new Error('fail')) });

    const result = await share(data);
    expect(result).toBe(false);
  });

  it('uses legacy execCommand fallback when navigator.clipboard is unavailable', async () => {
    const mockTextarea = {
      value: '',
      style: {} as CSSStyleDeclaration,
      select: vi.fn(),
    };
    vi.stubGlobal('navigator', {});
    vi.spyOn(document, 'createElement').mockReturnValue(mockTextarea as unknown as HTMLElement);
    vi.spyOn(document.body, 'appendChild').mockImplementation(() => mockTextarea as unknown as Node);
    vi.spyOn(document.body, 'removeChild').mockImplementation(() => mockTextarea as unknown as Node);
    document.execCommand = vi.fn().mockReturnValue(true);

    const result = await share(data);

    expect(result).toBe(true);
    expect(mockTextarea.value).toBe('https://example.com');
    expect(mockTextarea.select).toHaveBeenCalled();
    expect(document.execCommand).toHaveBeenCalledWith('copy');
    expect(document.body.removeChild).toHaveBeenCalled();
  });

  it('returns false when all share/clipboard methods fail', async () => {
    vi.stubGlobal('navigator', {});
    vi.spyOn(document, 'createElement').mockReturnValue({
      value: '',
      style: {} as CSSStyleDeclaration,
      select: vi.fn(),
    } as unknown as HTMLElement);
    vi.spyOn(document.body, 'appendChild').mockImplementation(() => {
      throw new Error('DOM error');
    });

    const result = await share(data);
    expect(result).toBe(false);
  });
});

describe('buildTrainShareData', () => {
  it('builds share data with train info', () => {
    const result = buildTrainShareData({
      trainId: '3515',
      origin: 'Trenton',
      destination: 'New York',
    });

    expect(result.title).toBe('Train 3515 - TrackRat');
    expect(result.text).toContain('Train 3515');
    expect(result.text).toContain('Trenton');
    expect(result.text).toContain('New York');
    expect(result.url).toContain('/train/3515');
  });

  it('includes from/to query params when provided', () => {
    const result = buildTrainShareData({
      trainId: '3515',
      origin: 'Trenton',
      destination: 'New York',
      from: 'TR',
      to: 'NY',
    });

    expect(result.url).toContain('from=TR');
    expect(result.url).toContain('to=NY');
  });

  it('includes date and data source when provided', () => {
    const result = buildTrainShareData({
      trainId: '3515',
      origin: 'Trenton',
      destination: 'New York',
      journeyDate: '2025-03-28',
      dataSource: 'NJT',
    });

    expect(result.url).toContain('date=2025-03-28');
    expect(result.url).toContain('data_source=NJT');
  });

  it('omits query params when from/to not provided', () => {
    const result = buildTrainShareData({
      trainId: '3515',
      origin: 'Trenton',
      destination: 'New York',
    });

    expect(result.url).not.toContain('?');
  });

  it('includes only from param when to is missing', () => {
    const result = buildTrainShareData({
      trainId: '3515',
      origin: 'Trenton',
      destination: 'New York',
      from: 'TR',
    });

    expect(result.url).toContain('from=TR');
    expect(result.url).not.toContain('to=');
  });
});
