import { useAuth } from "../auth/AuthContext";
import { PageHeader } from "../components/ui";
import { Link } from "../routes/router";

export function SecretaryDashboardPage() {
  const { user } = useAuth();
  return <>
    <PageHeader title={`سلام ${user?.first_name ?? ""}`} description="ثبت‌نام دانش‌آموزان، مشاهده پرونده‌ها و پیگیری پرداخت‌های هر دانش‌آموز." />
    <section className="card">
      <h2 className="card-title">عملیات ثبت‌نام</h2>
      <div className="button-row">
        <Link to="/students" className="button button--primary">ثبت‌نام دانش‌آموز</Link>
        <Link to="/student-records" className="button button--secondary">پرونده دانش‌آموزان</Link>
        <Link to="/courses" className="button button--secondary">دوره‌ها و شهریه‌ها</Link>
        <Link to="/tuition/due-payments" className="button button--secondary">پیگیری چک‌ها و اقساط</Link>
        <Link to="/tuition/outstanding" className="button button--secondary">پیگیری شهریه دانش‌آموز</Link>
      </div>
    </section>
  </>;
}
