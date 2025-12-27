/**
 * 路由配置
 */

import { createBrowserRouter, Navigate } from 'react-router-dom';
import { MainLayout } from '@/components/layout';
import { DashboardPage, UpdatesPage, UpdateDetailPage } from '@/pages';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <MainLayout />,
    children: [
      {
        index: true,
        element: <UpdatesPage />,
      },
      {
        path: 'updates',
        element: <Navigate to="/" replace />,
      },
      {
        path: 'dashboard',
        element: <DashboardPage />,
      },
      {
        path: 'updates/:id',
        element: <UpdateDetailPage />,
      },
    ],
  },
], {
  basename: import.meta.env.PROD ? '/next' : '/',
});
