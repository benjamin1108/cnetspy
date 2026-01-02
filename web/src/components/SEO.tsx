import { Helmet } from 'react-helmet-async';

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
  
  return (
    <Helmet>
      {/* Standard metadata */}
      <title>{fullTitle}</title>
      <meta name="description" content={description || 'CloudNetSpy 是一个专注于云厂商网络产品竞争情报分析的平台，提供实时更新追踪、深度对比分析和战略洞察。'} />
      
      {/* Open Graph / Facebook */}
      <meta property="og:type" content={type} />
      <meta property="og:title" content={title} />
      <meta property="og:description" content={description} />
      {image && <meta property="og:image" content={image} />}
      
      {/* Twitter */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={title} />
      <meta name="twitter:description" content={description} />
      {image && <meta name="twitter:image" content={image} />}
    </Helmet>
  );
}
