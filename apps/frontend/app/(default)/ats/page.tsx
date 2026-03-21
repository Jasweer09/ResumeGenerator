'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { PlatformSelector } from '@/components/ats/PlatformSelector';
import { ScoreCard } from '@/components/ats/ScoreCard';
import {
  detectATSPlatform,
  optimizeResumeForATS,
  type PlatformDetection,
  type ATSOptimizationResult,
} from '@/lib/api/ats';
import { Loader2, ArrowLeft, AlertTriangle, Sparkles } from 'lucide-react';
import Link from 'next/link';

export default function ATSOptimizePage() {
  const [jobDescription, setJobDescription] = useState('');
  const [jobUrl, setJobUrl] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [selectedPlatform, setSelectedPlatform] = useState('auto');
  const [detectedPlatform, setDetectedPlatform] = useState<PlatformDetection | undefined>();
  const [isDetecting, setIsDetecting] = useState(false);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ATSOptimizationResult | null>(null);
  const [masterResumeId, setMasterResumeId] = useState<string | null>(null);

  const router = useRouter();

  useEffect(() => {
    const storedId = localStorage.getItem('master_resume_id');
    if (!storedId) {
      router.push('/dashboard');
    } else {
      setMasterResumeId(storedId);
    }
  }, [router]);

  const handleTextareaKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter') e.stopPropagation();
  };

  // Auto-detect platform when job description, URL, or company changes
  useEffect(() => {
    if (!jobDescription.trim() && !jobUrl.trim()) {
      setDetectedPlatform(undefined);
      return;
    }

    const detectPlatform = async () => {
      if (isDetecting) return;

      setIsDetecting(true);
      try {
        const response = await detectATSPlatform({
          job_description: jobDescription || 'Placeholder for detection',
          job_url: jobUrl || undefined,
          company_name: companyName || undefined,
        });

        setDetectedPlatform(response.detection);

        // Auto-select detected platform if user hasn't manually chosen
        if (selectedPlatform === 'auto') {
          setSelectedPlatform(response.detection.platform);
        }
      } catch (err) {
        console.error('Platform detection failed:', err);
      } finally {
        setIsDetecting(false);
      }
    };

    // Debounce detection
    const timeoutId = setTimeout(detectPlatform, 1000);
    return () => clearTimeout(timeoutId);
  }, [jobDescription, jobUrl, companyName]);

  const handleOptimize = async () => {
    if (!masterResumeId || !jobDescription.trim()) return;

    setIsOptimizing(true);
    setError(null);
    setResult(null);

    try {
      const response = await optimizeResumeForATS({
        resume_id: masterResumeId,
        job_description: jobDescription,
        job_url: jobUrl || undefined,
        company_name: companyName || undefined,
        target_platform: selectedPlatform === 'auto' ? undefined : selectedPlatform,
        language: 'en',
        enable_cover_letter: true,
        max_refinement_iterations: 2,
        score_threshold: 85.0,
      });

      if (response.success && response.result) {
        setResult(response.result);
      } else {
        setError(response.error || 'Optimization failed');
      }
    } catch (err) {
      console.error('Optimization failed:', err);
      setError(err instanceof Error ? err.message : 'Optimization failed. Please try again.');
    } finally {
      setIsOptimizing(false);
    }
  };

  const handleViewResume = () => {
    if (result?.resume_id) {
      router.push(`/resumes/${result.resume_id}`);
    }
  };

  return (
    <div
      className="min-h-screen w-full bg-[#F6F5EE] flex flex-col items-center justify-start p-4 md:p-8 font-sans"
      style={{
        backgroundImage:
          'linear-gradient(rgba(29, 78, 216, 0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(29, 78, 216, 0.1) 1px, transparent 1px)',
        backgroundSize: '40px 40px',
      }}
    >
      <div className="w-full max-w-6xl">
        {/* Header */}
        <div className="mb-6 bg-white border border-black shadow-[8px_8px_0px_0px_rgba(0,0,0,0.1)] p-6 relative">
          <Button variant="link" className="absolute top-4 left-4" onClick={() => router.back()}>
            <ArrowLeft className="w-4 h-4" />
            Back
          </Button>

          <div className="text-center mt-4">
            <h1 className="font-serif text-4xl font-bold uppercase tracking-tight mb-2">
              ATS Optimizer
            </h1>
            <p className="font-mono text-sm text-blue-700 font-bold uppercase">
              {'// '} Generate Resume Optimized for Specific ATS Platforms
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Column: Input */}
          <div className="space-y-6">
            <div className="bg-white border border-black shadow-[8px_8px_0px_0px_rgba(0,0,0,0.1)] p-6">
              <h2 className="font-serif text-xl font-bold mb-4">Job Details</h2>

              <div className="space-y-4">
                {/* Job URL (optional) */}
                <div>
                  <label className="block font-mono text-sm font-medium mb-2">
                    Job Posting URL (Optional)
                  </label>
                  <input
                    type="url"
                    placeholder="https://boards.greenhouse.io/company/jobs/123"
                    className="w-full px-3 py-2 border-2 border-black rounded-none font-mono text-sm
                             focus:outline-none focus:ring-2 focus:ring-blue-700
                             disabled:opacity-50"
                    value={jobUrl}
                    onChange={(e) => setJobUrl(e.target.value)}
                    disabled={isOptimizing}
                  />
                  <p className="text-xs font-mono text-gray-600 mt-1">
                    Helps auto-detect ATS platform from URL
                  </p>
                </div>

                {/* Company Name (optional) */}
                <div>
                  <label className="block font-mono text-sm font-medium mb-2">
                    Company Name (Optional)
                  </label>
                  <input
                    type="text"
                    placeholder="Google, Amazon, Microsoft..."
                    className="w-full px-3 py-2 border-2 border-black rounded-none font-mono text-sm
                             focus:outline-none focus:ring-2 focus:ring-blue-700
                             disabled:opacity-50"
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    disabled={isOptimizing}
                  />
                  <p className="text-xs font-mono text-gray-600 mt-1">
                    Helps auto-detect from company database
                  </p>
                </div>

                {/* Job Description */}
                <div>
                  <label className="block font-mono text-sm font-medium mb-2">
                    Job Description *
                  </label>
                  <Textarea
                    placeholder="Paste the full job description here..."
                    className="min-h-[200px] font-mono text-sm bg-[#F0F0E8] border-2 border-black
                             focus:ring-0 focus:border-blue-700 resize-none p-4 rounded-none"
                    value={jobDescription}
                    onChange={(e) => setJobDescription(e.target.value)}
                    onKeyDown={handleTextareaKeyDown}
                    disabled={isOptimizing}
                  />
                  <div className="text-xs font-mono text-gray-400 mt-1">
                    {jobDescription.length} characters
                  </div>
                </div>

                {/* Platform Selector */}
                <PlatformSelector
                  selected={selectedPlatform}
                  onSelect={setSelectedPlatform}
                  detected={detectedPlatform}
                  disabled={isOptimizing}
                />

                {error && (
                  <div className="p-4 bg-red-50 border-2 border-red-600 text-red-700 text-sm font-mono">
                    <span className="font-bold">Error:</span> {error}
                  </div>
                )}

                <Button
                  size="lg"
                  onClick={handleOptimize}
                  disabled={isOptimizing || !jobDescription.trim() || !masterResumeId}
                  className="w-full"
                >
                  {isOptimizing ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Optimizing Resume...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-5 h-5" />
                      Generate ATS-Optimized Resume
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>

          {/* Right Column: Results */}
          <div>
            {result ? (
              <div className="bg-white border border-black shadow-[8px_8px_0px_0px_rgba(0,0,0,0.1)] p-6 space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="font-serif text-xl font-bold">Optimization Results</h2>
                  <span className="px-3 py-1 bg-green-700 text-white font-mono text-xs rounded-none">
                    SUCCESS
                  </span>
                </div>

                {/* Processing Info */}
                <div className="border-2 border-black p-3 bg-canvas">
                  <div className="grid grid-cols-2 gap-3 font-mono text-xs">
                    <div>
                      <span className="text-gray-600">Target Platform:</span>
                      <div className="font-bold mt-1">
                        {result.target_platform.charAt(0).toUpperCase() + result.target_platform.slice(1)}
                      </div>
                    </div>
                    <div>
                      <span className="text-gray-600">Processing Time:</span>
                      <div className="font-bold mt-1">{result.processing_time_seconds.toFixed(1)}s</div>
                    </div>
                  </div>

                  {result.refinement_performed && result.refinement_iterations.length > 0 && (
                    <div className="mt-3 pt-3 border-t-2 border-gray-300">
                      <div className="font-mono text-xs font-medium mb-2">Refinement:</div>
                      {result.refinement_iterations.map((iter, i) => (
                        <div key={i} className="font-mono text-xs text-gray-700">
                          Iteration {iter.iteration}: {iter.prev_score.toFixed(1)}% → {iter.new_score.toFixed(1)}%
                          <span className="text-green-700 ml-2">(+{iter.improvement.toFixed(1)}%)</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Recommendation */}
                <div className="border-2 border-blue-700 bg-blue-50 p-4">
                  <div className="font-mono text-xs font-bold uppercase text-blue-700 mb-2">
                    Recommendation
                  </div>
                  <p className="font-sans text-sm text-blue-900">{result.recommendation}</p>
                </div>

                {/* Scores */}
                <ScoreCard scores={result.final_scores} showDetails={true} />

                {/* Actions */}
                <div className="flex gap-3 pt-4">
                  <Button onClick={handleViewResume} className="flex-1">
                    View Optimized Resume
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setResult(null);
                      setJobDescription('');
                      setJobUrl('');
                      setCompanyName('');
                      setSelectedPlatform('auto');
                    }}
                  >
                    Optimize Another
                  </Button>
                </div>
              </div>
            ) : (
              <div className="bg-white border border-black shadow-[8px_8px_0px_0px_rgba(0,0,0,0.1)] p-6">
                <h2 className="font-serif text-xl font-bold mb-4">How It Works</h2>
                <div className="space-y-4 font-sans text-sm">
                  <div className="flex gap-3">
                    <span className="font-mono font-bold text-blue-700">1.</span>
                    <div>
                      <p className="font-semibold">Platform Detection</p>
                      <p className="text-gray-600 text-xs mt-1">
                        Automatically detects ATS from URL or company name
                      </p>
                    </div>
                  </div>

                  <div className="flex gap-3">
                    <span className="font-mono font-bold text-blue-700">2.</span>
                    <div>
                      <p className="font-semibold">Platform-Specific Generation</p>
                      <p className="text-gray-600 text-xs mt-1">
                        Optimizes resume using platform-specific algorithms
                      </p>
                    </div>
                  </div>

                  <div className="flex gap-3">
                    <span className="font-mono font-bold text-blue-700">3.</span>
                    <div>
                      <p className="font-semibold">Multi-Platform Scoring</p>
                      <p className="text-gray-600 text-xs mt-1">
                        Tests compatibility across all 6 major ATS platforms
                      </p>
                    </div>
                  </div>

                  <div className="flex gap-3">
                    <span className="font-mono font-bold text-blue-700">4.</span>
                    <div>
                      <p className="font-semibold">Intelligent Refinement</p>
                      <p className="text-gray-600 text-xs mt-1">
                        Automatically refines until 85%+ score achieved
                      </p>
                    </div>
                  </div>
                </div>

                <div className="mt-6 border-2 border-gray-300 p-4 bg-gray-50">
                  <p className="font-mono text-xs font-bold mb-2">Supported Platforms:</p>
                  <ul className="font-mono text-xs text-gray-700 space-y-1">
                    <li>• Workday (45% of Fortune 500)</li>
                    <li>• Greenhouse (Tech startups)</li>
                    <li>• Taleo (Oracle - Enterprise)</li>
                    <li>• iCIMS (Global leader)</li>
                    <li>• Lever (Modern recruiting)</li>
                    <li>• SAP SuccessFactors</li>
                  </ul>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
