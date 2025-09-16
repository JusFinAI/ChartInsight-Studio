import { formatDistanceToNow, parseISO } from 'date-fns';
import { Badge } from '@/components/ui/Badge';
import { ExternalLink } from 'lucide-react';

interface NewsItemProps {
  title: string;
  source: string;
  date: string;
  url: string;
  sentiment: 'positive' | 'negative' | 'neutral';
}

const NewsItem = ({ title, source, date, url, sentiment }: NewsItemProps) => {
  // 뉴스 발행일 형식화
  const formattedDate = () => {
    try {
      return formatDistanceToNow(parseISO(date), { addSuffix: true });
    } catch (err) {
      return '알 수 없는 날짜';
    }
  };

  // 센티먼트 배지 구하기
  const getSentimentBadge = () => {
    switch (sentiment) {
      case 'positive':
        return <Badge variant="success">긍정적</Badge>;
      case 'negative':
        return <Badge variant="error">부정적</Badge>;
      case 'neutral':
      default:
        return <Badge variant="secondary">중립</Badge>;
    }
  };

  return (
    <div className="flex items-start justify-between p-2 border rounded-md">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <p className="font-medium">{title}</p>
          {getSentimentBadge()}
        </div>
        <div className="flex text-xs text-gray-500 gap-2">
          <span>{source}</span>
          <span>•</span>
          <span>{formattedDate()}</span>
        </div>
      </div>
      <a href={url} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:text-blue-700">
        <ExternalLink className="h-4 w-4" />
      </a>
    </div>
  );
};

export default NewsItem; 