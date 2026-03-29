import React from 'react';
import type {
  ResumeData,
  SectionMeta,
  CustomSection,
  CustomSectionItem,
} from '@/components/dashboard/resume-component';
import { formatDateRange } from '@/lib/utils';
import { SafeHtml } from './safe-html';
import baseStyles from './styles/_base.module.css';

interface DynamicResumeSectionProps {
  sectionMeta: SectionMeta;
  resumeData: ResumeData;
}

/**
 * DynamicResumeSection Component
 *
 * Renders custom sections in resume templates based on section type.
 * Uses the same CSS classes as built-in sections for consistent styling.
 */
export const DynamicResumeSection: React.FC<DynamicResumeSectionProps> = ({
  sectionMeta,
  resumeData,
}) => {
  // Get the custom section data
  const customSection = resumeData.customSections?.[sectionMeta.key];

  if (!customSection) return null;

  // Check if section has content
  const hasContent = (() => {
    switch (sectionMeta.sectionType) {
      case 'text':
        return Boolean(customSection.text?.trim());
      case 'itemList':
        return Boolean(customSection.items?.length);
      case 'stringList':
        return Boolean(customSection.strings?.length);
      default:
        return false;
    }
  })();

  if (!hasContent) return null;

  return (
    <div className={baseStyles['resume-section']}>
      <h3 className={baseStyles['resume-section-title']}>{sectionMeta.displayName}</h3>
      {renderContent(sectionMeta.sectionType, customSection)}
    </div>
  );
};

/**
 * Render section content based on type
 */
function renderContent(sectionType: SectionMeta['sectionType'], customSection: CustomSection) {
  switch (sectionType) {
    case 'text':
      return <TextSectionContent text={customSection.text || ''} />;
    case 'itemList':
      return <ItemListSectionContent items={customSection.items || []} />;
    case 'stringList':
      return <StringListSectionContent strings={customSection.strings || []} />;
    default:
      return null;
  }
}

/**
 * Text Section Content (like Summary)
 */
const TextSectionContent: React.FC<{ text: string }> = ({ text }) => {
  if (!text.trim()) return null;

  return <p className={`text-justify ${baseStyles['resume-text']}`}>{text}</p>;
};

/**
 * Item List Section Content (like Experience)
 */
const ItemListSectionContent: React.FC<{ items: CustomSectionItem[] }> = ({ items }) => {
  if (items.length === 0) return null;

  return (
    <div className={baseStyles['resume-items']}>
      {items.map((item) => (
        <div key={item.id} className={baseStyles['resume-item']}>
          {/* Title and Years Row */}
          <div className={`flex justify-between items-baseline ${baseStyles['resume-row-tight']}`}>
            <h4 className={baseStyles['resume-item-title']}>{item.title}</h4>
            {item.years && (
              <span className={`${baseStyles['resume-meta-sm']} shrink-0 ml-4`}>
                {formatDateRange(item.years)}
              </span>
            )}
          </div>

          {/* Subtitle and Location Row */}
          {(item.subtitle || item.location) && (
            <div
              className={`flex justify-between items-center ${baseStyles['resume-row']} ${baseStyles['resume-item-subtitle']}`}
            >
              {item.subtitle && <span>{item.subtitle}</span>}
              {item.location && <span>{item.location}</span>}
            </div>
          )}

          {/* Description Points */}
          {item.description && item.description.length > 0 && (
            <ul className={`ml-4 ${baseStyles['resume-list']} ${baseStyles['resume-text-sm']}`}>
              {item.description.map((desc, index) => (
                <li key={index} className="flex">
                  <span className="mr-1.5 flex-shrink-0">•&nbsp;</span>
                  <span>
                    <SafeHtml html={desc} />
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
};

/**
 * String List Section Content (like Skills) - Enhanced for categories
 */
const StringListSectionContent: React.FC<{ strings: string[] }> = ({ strings }) => {
  if (strings.length === 0) return null;

  // Check if skills have categories (e.g., "Programming Languages: Python, Java")
  const hasCategories = strings.some(s => s.includes(':'));

  if (hasCategories) {
    // Display with category formatting (each category on new line)
    return (
      <div className={baseStyles['resume-text-sm']}>
        {strings.map((skillLine, idx) => {
          if (skillLine.includes(':')) {
            const [category, items] = skillLine.split(':', 2);
            return (
              <div key={idx} className="mb-1">
                <span className="font-bold">{category}:</span>{' '}
                <span>{items.trim()}</span>
              </div>
            );
          } else {
            // Fallback for non-categorized items
            return <span key={idx}>{skillLine}, </span>;
          }
        })}
      </div>
    );
  }

  // Original behavior for non-categorized skills (backward compatibility)
  return <div className={baseStyles['resume-text-sm']}>{strings.join(', ')}</div>;
};

export default DynamicResumeSection;
