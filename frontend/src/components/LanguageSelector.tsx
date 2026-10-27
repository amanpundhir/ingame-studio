/**
 * InGame Studio - Multi-Language Storytelling Selector
 * InGame design-system compliant — all inline styles replaced with token classes.
 */

import React from 'react';
import { LanguageCode } from '../types';

interface LanguageSelectorProps {
  currentLanguage: LanguageCode;
  onSelectLanguage: (lang: LanguageCode) => void;
}

const LANGUAGES: { code: LanguageCode; label: string; flag: string }[] = [
  { code: 'en', label: 'EN', flag: '🇬🇧' },
  { code: 'es', label: 'ES', flag: '🇪🇸' },
];

export const LanguageSelector: React.FC<LanguageSelectorProps> = ({
  currentLanguage,
  onSelectLanguage,
}) => {
  return (
    <div className="lang-selector" role="group" aria-label="Select commentary language">
      <span className="lang-selector-label" aria-hidden="true">Lang:</span>
      <div className="lang-pill-group">
        {LANGUAGES.map((lang) => {
          const isActive = currentLanguage === lang.code;
          return (
            <button
              key={lang.code}
              onClick={() => onSelectLanguage(lang.code)}
              className={`lang-pill${isActive ? ' active' : ''}`}
              aria-pressed={isActive}
              aria-label={`Switch to ${lang.label} commentary`}
              title={lang.label}
            >
              <span aria-hidden="true">{lang.flag}</span>
              <span>{lang.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
};
