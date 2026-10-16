import { ImageResponse } from 'next/og';

// The home-screen icon on iPhones. iOS rounds the corners itself, so the tile fills the square.
export const size = { width: 180, height: 180 };
export const contentType = 'image/png';

export default function AppleIcon() {
  return new ImageResponse(
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(to bottom, #ff8763, #ff5b3a)'
      }}
    >
      {/* The noodle from the brand mark */}
      <svg width="120" height="120" viewBox="0 0 24 24" fill="none">
        <path
          d="M3 15.5c1.6 -5 4.4 -5 5.2 -1.8c0.7 2.9 3.3 3 4.3 -0.7c0.6 -2.1 1.6 -3 3 -3H21"
          stroke="#fff"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>,
    size
  );
}
