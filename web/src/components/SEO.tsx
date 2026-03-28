import { useEffect } from 'react';

interface SEOProps {
  title: string;
  description?: string;
  type?: string;
  name?: string;
  image?: string;
}

export function SEO({ title, description, type = 'article', name = 'CloudNetSpy', image }: SEOProps) {
  const siteTitle = 'CloudNetSpy - 云竞争情报分析平台';
  const fullTitle = title === siteTitle ? title : `${title} | ${name}`;
  const resolvedDescription =
    description || 'CloudNetSpy 是一个专注于云厂商网络产品竞争情报分析的平台，提供实时更新追踪、深度对比分析和战略洞察。';

  useEffect(() => {
    const previousTitle = document.title;
    document.title = fullTitle;

    const upsertMeta = (selector: string, attributes: Record<string, string>, content?: string) => {
      const head = document.head;
      let element = document.querySelector(selector) as HTMLMetaElement | null;
      const created = !element;

      if (!element) {
        element = document.createElement('meta');
        Object.entries(attributes).forEach(([key, value]) => element!.setAttribute(key, value));
      }

      if (content) {
        element.setAttribute('content', content);
      } else if (element.hasAttribute('content')) {
        element.removeAttribute('content');
      }

      if (created) {
        head.appendChild(element);
      }

      return { element, created };
    };

    const metas = [
      upsertMeta('meta[name="description"]', { name: 'description' }, resolvedDescription),
      upsertMeta('meta[property="og:type"]', { property: 'og:type' }, type),
      upsertMeta('meta[property="og:title"]', { property: 'og:title' }, title),
      upsertMeta('meta[property="og:description"]', { property: 'og:description' }, resolvedDescription),
      upsertMeta('meta[property="og:image"]', { property: 'og:image' }, image),
      upsertMeta('meta[name="twitter:card"]', { name: 'twitter:card' }, 'summary_large_image'),
      upsertMeta('meta[name="twitter:title"]', { name: 'twitter:title' }, title),
      upsertMeta('meta[name="twitter:description"]', { name: 'twitter:description' }, resolvedDescription),
      upsertMeta('meta[name="twitter:image"]', { name: 'twitter:image' }, image),
    ];

    return () => {
      document.title = previousTitle;
      metas.forEach(({ element, created }) => {
        if (created) {
          element.remove();
        }
      });
    };
  }, [fullTitle, image, resolvedDescription, title, type]);

  return null;
}
