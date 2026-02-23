/**
 * Component tests for Sidebar - Tests T144-TEST
 * Validates navigation links
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Sidebar } from '../../../src/components/Layout/Sidebar';

describe('Sidebar Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderWithRouter = (initialRoute: string = '/'): void => {
    render(
      <MemoryRouter initialEntries={[initialRoute]}>
        <Sidebar />
      </MemoryRouter>
    );
  };

  it('should display navigation links', () => {
    renderWithRouter();

    const dashboardLink: HTMLElement = screen.getByRole('link', { name: /dashboard/i });
    const queryLink: HTMLElement = screen.getByRole('link', { name: /query/i });
    const datasetsLink: HTMLElement = screen.getByRole('link', { name: /datasets/i });
    const historyLink: HTMLElement = screen.getByRole('link', { name: /history/i });

    expect(dashboardLink).toBeInTheDocument();
    expect(queryLink).toBeInTheDocument();
    expect(datasetsLink).toBeInTheDocument();
    expect(historyLink).toBeInTheDocument();
  });

  it('should have link to Query page', () => {
    renderWithRouter();

    const queryLink: HTMLElement = screen.getByRole('link', { name: /query/i });
    expect(queryLink).toHaveAttribute('href', '/query');
  });

  it('should have link to Datasets page', () => {
    renderWithRouter();

    const datasetsLink: HTMLElement = screen.getByRole('link', { name: /datasets/i });
    expect(datasetsLink).toHaveAttribute('href', '/datasets');
  });

  it('should have link to History page', () => {
    renderWithRouter();

    const historyLink: HTMLElement = screen.getByRole('link', { name: /history/i });
    expect(historyLink).toHaveAttribute('href', '/history');
  });

  it('should highlight active route', () => {
    renderWithRouter('/query');

    const queryLink: HTMLElement = screen.getByRole('link', { name: /query/i });
    expect(queryLink.className).toContain('active');
  });

  it('should have correct navigation structure', () => {
    renderWithRouter();

    const nav: HTMLElement = screen.getByRole('navigation');
    expect(nav).toBeInTheDocument();

    const links: HTMLElement[] = screen.getAllByRole('link');
    expect(links).toHaveLength(4);
  });
});
