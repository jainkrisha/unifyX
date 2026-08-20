import React from 'react';

interface ApiErrorBannerProps {
  status?: number;
  detail: string;
}

export function ApiErrorBanner({ status, detail }: ApiErrorBannerProps) {
  const is403 = status === 403;
  const is401 = status === 401;

  return (
    <div className={`banner banner-error`} role="alert">
      <span className="banner-icon">
        {is403 ? '🔒' : is401 ? '🔑' : '⚠️'}
      </span>
      <div>
        <strong>
          {is403
            ? 'Access denied (403 Forbidden)'
            : is401
            ? 'Not authenticated (401)'
            : `Error${status ? ` (${status})` : ''}`}
        </strong>
        <br />
        <span style={{ marginTop: 2, display: 'block', opacity: 0.85 }}>{detail}</span>
        {is403 && (
          <span style={{ display: 'block', marginTop: 4, fontSize: 12, opacity: 0.7 }}>
            The backend enforces this restriction — the UI simply reflects the API response.
          </span>
        )}
      </div>
    </div>
  );
}
