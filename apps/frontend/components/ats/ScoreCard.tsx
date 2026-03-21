/**
 * ATS Score Card Component
 * Displays multi-platform ATS scores with detailed breakdown
 */

import type { MultiPlatformScores, PlatformScore } from '@/lib/api/ats';

interface ScoreCardProps {
  scores: MultiPlatformScores;
  showDetails?: boolean;
}

function getScoreColor(score: number): string {
  if (score >= 85) return 'bg-green-700 text-white';
  if (score >= 75) return 'bg-blue-700 text-white';
  if (score >= 70) return 'bg-orange-600 text-white';
  return 'bg-red-600 text-white';
}

function getScoreLabel(score: number): string {
  if (score >= 90) return 'Excellent';
  if (score >= 85) return 'Very Good';
  if (score >= 80) return 'Good';
  if (score >= 75) return 'Fair';
  return 'Needs Work';
}

function ScoreBadge({ score }: { score: number }) {
  return (
    <span className={`px-3 py-1 font-mono text-sm font-bold rounded-none ${getScoreColor(score)}`}>
      {score.toFixed(0)}%
    </span>
  );
}

function PlatformScoreRow({
  platform,
  score,
  isTarget,
  showDetails,
}: {
  platform: PlatformScore;
  isTarget: boolean;
  showDetails: boolean;
}) {
  return (
    <div className="border-2 border-black p-3 bg-white">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="font-sans text-base font-medium">
            {platform.platform.charAt(0).toUpperCase() + platform.platform.slice(1)}
          </span>
          {isTarget && (
            <span className="px-2 py-0.5 bg-blue-700 text-white font-mono text-xs rounded-none">
              TARGET
            </span>
          )}
        </div>
        <ScoreBadge score={platform.score} />
      </div>

      {showDetails && (
        <div className="space-y-2 mt-3 pt-3 border-t-2 border-gray-300">
          <div className="grid grid-cols-2 gap-3 font-mono text-xs">
            <div>
              <span className="text-gray-600">Keyword Match:</span>
              <span className="ml-2 font-bold">{platform.keyword_match.toFixed(0)}%</span>
            </div>
            <div>
              <span className="text-gray-600">Format Score:</span>
              <span className="ml-2 font-bold">{platform.format_score.toFixed(0)}%</span>
            </div>
          </div>

          <div className="font-mono text-xs text-gray-600">
            Algorithm: {platform.algorithm}
          </div>

          {platform.strengths.length > 0 && (
            <div className="mt-2">
              <div className="font-mono text-xs font-medium text-green-700 mb-1">Strengths:</div>
              <ul className="font-sans text-xs space-y-0.5 pl-4">
                {platform.strengths.map((s, i) => (
                  <li key={i} className="text-green-800">✓ {s}</li>
                ))}
              </ul>
            </div>
          )}

          {platform.weaknesses.length > 0 && (
            <div className="mt-2">
              <div className="font-mono text-xs font-medium text-red-700 mb-1">Weaknesses:</div>
              <ul className="font-sans text-xs space-y-0.5 pl-4">
                {platform.weaknesses.map((w, i) => (
                  <li key={i} className="text-red-800">⚠ {w}</li>
                ))}
              </ul>
            </div>
          )}

          {platform.missing_keywords.length > 0 && (
            <div className="mt-2">
              <div className="font-mono text-xs font-medium mb-1">Missing Keywords:</div>
              <div className="flex flex-wrap gap-1">
                {platform.missing_keywords.slice(0, 10).map((kw, i) => (
                  <span
                    key={i}
                    className="px-2 py-0.5 bg-red-100 border border-red-300 font-mono text-xs rounded-none"
                  >
                    {kw}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ScoreCard({ scores, showDetails = false }: ScoreCardProps) {
  const platformOrder = ['taleo', 'workday', 'successfactors', 'lever', 'greenhouse', 'icims'];

  return (
    <div className="space-y-4">
      {/* Overall Summary */}
      <div className="border-2 border-black p-4 bg-canvas">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-serif text-lg font-bold">ATS Compatibility Analysis</h3>
          <ScoreBadge score={scores.average_score} />
        </div>

        <div className="grid grid-cols-3 gap-4 font-mono text-xs">
          <div>
            <span className="text-gray-600 block mb-1">Best Platform:</span>
            <span className="font-bold">
              {scores.best_platform.charAt(0).toUpperCase() + scores.best_platform.slice(1)}
            </span>
          </div>
          <div>
            <span className="text-gray-600 block mb-1">Average Score:</span>
            <span className="font-bold">{scores.average_score.toFixed(1)}%</span>
          </div>
          <div>
            <span className="text-gray-600 block mb-1">All Platforms 75%+:</span>
            <span className={`font-bold ${scores.all_platforms_above_threshold ? 'text-green-700' : 'text-orange-600'}`}>
              {scores.all_platforms_above_threshold ? 'Yes ✓' : 'No'}
            </span>
          </div>
        </div>
      </div>

      {/* Platform-Specific Scores */}
      <div className="space-y-2">
        <h4 className="font-mono text-sm font-medium">Platform Breakdown:</h4>
        {platformOrder.map((platformKey) => {
          const platformScore = scores.scores[platformKey];
          if (!platformScore) return null;

          return (
            <PlatformScoreRow
              key={platformKey}
              platform={platformScore}
              isTarget={platformKey === scores.target_platform}
              showDetails={showDetails}
            />
          );
        })}
      </div>
    </div>
  );
}
