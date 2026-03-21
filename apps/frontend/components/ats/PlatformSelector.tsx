/**
 * ATS Platform Selector Component
 * Allows users to select target ATS platform or auto-detect
 */

import { ATS_PLATFORMS, type ATSPlatform, type PlatformDetection } from '@/lib/api/ats';

interface PlatformSelectorProps {
  selected: string;
  onSelect: (platform: string) => void;
  detected?: PlatformDetection;
  disabled?: boolean;
}

const CONFIDENCE_BADGES = {
  verified: { label: 'Verified', className: 'bg-green-700 text-white' },
  high: { label: 'High Confidence', className: 'bg-blue-700 text-white' },
  medium: { label: 'Medium Confidence', className: 'bg-orange-600 text-white' },
  low: { label: 'Low Confidence', className: 'bg-gray-600 text-white' },
  unknown: { label: 'Unknown', className: 'bg-gray-500 text-white' },
};

export function PlatformSelector({
  selected,
  onSelect,
  detected,
  disabled = false,
}: PlatformSelectorProps) {
  return (
    <div className="space-y-3">
      <div>
        <label htmlFor="ats-platform" className="block font-mono text-sm font-medium mb-2">
          Target ATS Platform
        </label>
        <select
          id="ats-platform"
          value={selected}
          onChange={(e) => onSelect(e.target.value)}
          disabled={disabled}
          className="w-full px-3 py-2 border-2 border-black rounded-none font-mono text-sm
                     focus:outline-none focus:ring-2 focus:ring-blue-700
                     disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {ATS_PLATFORMS.map((platform) => (
            <option key={platform.value} value={platform.value}>
              {platform.label}
            </option>
          ))}
        </select>
      </div>

      {detected && detected.confidence !== 'unknown' && (
        <div className="border-2 border-black p-3 bg-canvas">
          <div className="flex items-start gap-2">
            <div className="flex-1">
              <div className="font-mono text-xs font-medium mb-1">Auto-detected:</div>
              <div className="font-sans text-sm">
                {ATS_PLATFORMS.find((p) => p.value === detected.platform)?.label || detected.platform}
              </div>
              {detected.company_name && (
                <div className="font-mono text-xs text-gray-600 mt-1">
                  Company: {detected.company_name}
                </div>
              )}
              <div className="font-mono text-xs text-gray-600 mt-1">
                Source: {detected.source.replace('_', ' ')}
              </div>
            </div>
            <span
              className={`px-2 py-1 font-mono text-xs rounded-none ${
                CONFIDENCE_BADGES[detected.confidence as keyof typeof CONFIDENCE_BADGES]?.className ||
                CONFIDENCE_BADGES.unknown.className
              }`}
            >
              {CONFIDENCE_BADGES[detected.confidence as keyof typeof CONFIDENCE_BADGES]?.label ||
                detected.confidence}
            </span>
          </div>
        </div>
      )}

      <div className="text-xs font-mono text-gray-600">
        <details className="cursor-pointer">
          <summary className="font-medium hover:text-black">Platform differences</summary>
          <ul className="mt-2 space-y-1 pl-4">
            <li>• <span className="font-medium">Taleo:</span> Strictest - requires exact keyword matches</li>
            <li>• <span className="font-medium">Workday:</span> Strict - combines exact + semantic matching</li>
            <li>• <span className="font-medium">iCIMS:</span> Most forgiving - focuses on semantic understanding</li>
            <li>• <span className="font-medium">Greenhouse:</span> Lenient - prioritizes human review</li>
            <li>• <span className="font-medium">Lever:</span> Medium - uses stemming for variations</li>
            <li>• <span className="font-medium">SuccessFactors:</span> Medium - normalizes skill taxonomy</li>
          </ul>
        </details>
      </div>
    </div>
  );
}
