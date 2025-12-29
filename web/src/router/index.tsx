/**
 * 路由配置
 */

import { createBrowserRouter } from 'react-router-dom';
import { MainLayout } from '@/components/layout';
import { DashboardPage, HomePage, UpdatesPage, UpdateDetailPage, ReportsPage } from '@/pages';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <MainLayout />,
    children: [
      {
        index: true,
        element: <HomePage />,
      },
      {
        path: 'updates',
        element: <UpdatesPage />,
      },
      {
        path: 'dashboard',
        element: <DashboardPage />,
      },
      {
        path: 'updates/:id',
        element: <UpdateDetailPage />,
      },
      {
        path: 'reports',
        element: <ReportsPage />,
      },
    ],
  },
], {
  basename: import.meta.env.PROD ? '/next' : '/',
});
