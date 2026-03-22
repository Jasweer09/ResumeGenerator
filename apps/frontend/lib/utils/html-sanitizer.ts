/**
 * Whitelist of allowed HTML tags for rich text content
 */
const ALLOWED_TAGS = ['strong', 'em', 'u', 'a'];

/**
 * Whitelist of allowed HTML attributes
 */
const ALLOWED_ATTR = ['href', 'target', 'rel'];

/**
 * Simple client-side HTML sanitizer (fallback when DOMPurify not available)
 */
function sanitizeHtmlFallback(dirty: string): string {
  // Simple regex-based sanitization (basic security)
  return dirty
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
    .replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, '')
    .replace(/on\w+\s*=\s*["'][^"']*["']/gi, ''); // Remove event handlers
}

/**
 * Sanitizes HTML content using DOMPurify with a strict whitelist.
 * Only allows bold, italic, underline, and link formatting.
 * Client-side only to avoid SSR ESM issues.
 *
 * @param dirty - The unsanitized HTML string
 * @returns Sanitized HTML string safe for rendering
 */
export function sanitizeHtml(dirty: string): string {
  // Client-side only (avoid SSR ESM issues)
  if (typeof window === 'undefined') {
    return sanitizeHtmlFallback(dirty);
  }

  try {
    // Dynamic import for client-side only
    const DOMPurify = require('isomorphic-dompurify');
    return DOMPurify.sanitize(dirty, {
      ALLOWED_TAGS,
      ALLOWED_ATTR,
      FORCE_BODY: true,
    });
  } catch (e) {
    console.warn('DOMPurify not available, using fallback sanitizer');
    return sanitizeHtmlFallback(dirty);
  }
}

/**
 * Strips all HTML tags from content, returning plain text.
 *
 * @param html - HTML string to strip
 * @returns Plain text with all tags removed
 */
export function stripHtml(html: string): string {
  // Client-side only
  if (typeof window === 'undefined') {
    return html.replace(/<[^>]*>/g, '');
  }

  try {
    const DOMPurify = require('isomorphic-dompurify');
    return DOMPurify.sanitize(html, { ALLOWED_TAGS: [] });
  } catch (e) {
    return html.replace(/<[^>]*>/g, '');
  }
}

/**
 * Checks if a string contains HTML tags.
 *
 * @param text - String to check
 * @returns True if the string contains HTML tags
 */
export function isHtmlContent(text: string): boolean {
  return /<[a-z][\s\S]*>/i.test(text);
}
