/**
 * NeonCheckbox — Custom wireframe neon checkbox.
 *
 * Renders a hidden native <input type="checkbox"> for accessibility
 * (keyboard, form submission, screen-readers) overlaid by an SVG
 * wireframe box with an animated check-mark stroke.
 */

import React from 'react';
import './NeonCheckbox.css';

export type NeonCheckboxColor = 'cyan' | 'orange' | 'gold' | 'green' | 'pink';

interface NeonCheckboxProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  color?: NeonCheckboxColor;
  /** Forwarded to the native input for accessibility. */
  ariaLabel?: string;
}

export const NeonCheckbox: React.FC<NeonCheckboxProps> = ({
  checked,
  onChange,
  disabled = false,
  color = 'cyan',
  ariaLabel,
}) => {
  const cls: string = [
    'neon-checkbox',
    checked ? 'checked' : '',
    disabled ? 'disabled' : '',
  ].filter(Boolean).join(' ');

  return (
    <span className={cls} data-color={color}>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e: React.ChangeEvent<HTMLInputElement>): void => {
          onChange(e.target.checked);
        }}
        disabled={disabled}
        aria-label={ariaLabel}
      />
      <svg className="neon-checkbox-icon" viewBox="0 0 18 18" aria-hidden="true">
        {/* Outer box */}
        <rect
          className="ncb-box"
          x="1.5" y="1.5"
          width="15" height="15"
          rx="2"
          strokeWidth="1.2"
        />
        {/* Check mark */}
        <polyline
          className="ncb-check"
          points="5,9.5 8,13 13.5,5.5"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
};
