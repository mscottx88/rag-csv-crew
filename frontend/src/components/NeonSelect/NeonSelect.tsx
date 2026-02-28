/**
 * NeonSelect — Custom keyboard-accessible dropdown.
 * Replaces native <select> so the CursorSnake custom cursor remains active
 * and the LightningBorder effect works correctly.
 */

import React, { useState, useRef, useEffect } from 'react';
import './NeonSelect.css';

export interface NeonSelectOption {
  value: string;
  label: string;
}

interface NeonSelectProps {
  value: string;
  onChange: (value: string) => void;
  options: NeonSelectOption[];
  /** Theme accent colour. Defaults to 'gold'. */
  color?: 'gold' | 'orange';
  id?: string;
}

/** Duration of the close animation in milliseconds. */
const CLOSE_ANIM_MS: number = 500;

export const NeonSelect: React.FC<NeonSelectProps> = ({
  value,
  onChange,
  options,
  color = 'gold',
  id,
}) => {
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [closing, setClosing] = useState<boolean>(false);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const closingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const currentLabel: string =
    options.find((o: NeonSelectOption) => o.value === value)?.label ?? value;

  const handleToggle = (): void => {
    if (closing) return; // ignore clicks during close animation
    setIsOpen((prev: boolean) => !prev);
  };

  const handleSelect = (optionValue: string): void => {
    if (closing) return;
    onChange(optionValue);
    setClosing(true);
    closingTimerRef.current = setTimeout((): void => {
      setIsOpen(false);
      setClosing(false);
      closingTimerRef.current = null;
    }, CLOSE_ANIM_MS);
  };

  // Cleanup timer on unmount
  useEffect(() => {
    return (): void => {
      if (closingTimerRef.current) {
        clearTimeout(closingTimerRef.current);
      }
    };
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent): void => {
    if (e.key === 'Escape') {
      setIsOpen(false);
      setClosing(false);
      if (closingTimerRef.current) {
        clearTimeout(closingTimerRef.current);
        closingTimerRef.current = null;
      }
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      if (!closing) setIsOpen((prev: boolean) => !prev);
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      const idx: number = options.findIndex((o: NeonSelectOption) => o.value === value);
      const next: NeonSelectOption | undefined = options[idx + 1] ?? options[0];
      if (next) onChange(next.value);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      const idx: number = options.findIndex((o: NeonSelectOption) => o.value === value);
      const prev: NeonSelectOption | undefined = options[idx - 1] ?? options[options.length - 1];
      if (prev) onChange(prev.value);
    }
  };

  // Close on outside click
  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (e: MouseEvent): void => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setIsOpen(false);
        setClosing(false);
        if (closingTimerRef.current) {
          clearTimeout(closingTimerRef.current);
          closingTimerRef.current = null;
        }
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  return (
    <div
      ref={wrapperRef}
      className={`neon-select-custom neon-select-${color}`}
    >
      <button
        id={id}
        type="button"
        className="neon-select-trigger"
        onClick={handleToggle}
        onKeyDown={handleKeyDown}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        <span className="neon-select-value">{currentLabel}</span>
        <svg
          className={`neon-select-chevron${isOpen && !closing ? ' open' : ''}`}
          width="10"
          height="10"
          viewBox="0 0 10 10"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M2 3.5 L5 7 L8 3.5"
            stroke="currentColor"
            strokeWidth="1.2"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        </svg>
      </button>

      {isOpen && (
        <ul
          className={`neon-select-dropdown${closing ? ' closing' : ''}`}
          role="listbox"
          onClick={(e: React.MouseEvent): void => { e.stopPropagation(); }}
        >
          {options.map((option: NeonSelectOption) => (
            <li
              key={option.value}
              className={`neon-select-option${option.value === value ? ' selected' : ''}`}
              role="option"
              aria-selected={option.value === value}
              onClick={(): void => handleSelect(option.value)}
            >
              {option.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
