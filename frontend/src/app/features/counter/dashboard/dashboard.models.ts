export interface MovementDay {
  date: string;
  loans: number;
  returns: number;
}
export interface CategoryCount {
  name: string;
  count: number;
}
export interface PopularBook {
  id: number;
  title: string;
  author: string;
  cover_url: string | null;
  loans: number;
  reservations: number;
}
export interface RecentMovement {
  id: number;
  book_id: number;
  title: string;
  client: string;
  date: string;
  due_date: string;
  returned_at: string | null;
  status: string;
}
export interface DashboardOverview {
  loans_today: number;
  week: MovementDay[];
  categories: CategoryCount[];
  popular: PopularBook[];
  recent_loans: RecentMovement[];
  recent_returns: RecentMovement[];
}
