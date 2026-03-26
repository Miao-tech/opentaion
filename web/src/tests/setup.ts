// web/src/tests/setup.ts
import "@testing-library/jest-dom";

// Recharts uses ResizeObserver — mock it for jsdom
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};
