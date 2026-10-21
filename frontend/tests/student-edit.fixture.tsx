import { createRoot } from "react-dom/client";
import { ThemeProvider } from "../src/theme/ThemeContext";
import { StudentEditModal } from "../src/pages/StudentEditModal";
import type { Student } from "../src/types/api";
const student: Student = { id: "synthetic-only", full_name: "Synthetic Student", national_id: "1234567890", birth_date: "2013-01-01", grade: "GRADE_7", student_phone: null, registration_date: "2026-09-23", first_exam_date: null, academic_track: null, book_voucher_eligible: false, exam_registered: false, guardian_full_name: "Synthetic Father", guardian_phone: "09120000000", mother_full_name: null, mother_phone: null, address: null, previous_school: null, emergency_contact: null, notes: null, created_by_id: "synthetic-actor", enrollments: [] };
createRoot(document.getElementById("root")!).render(<ThemeProvider><StudentEditModal student={student} close={() => {}} saved={() => { document.body.dataset.saved = "true"; }} /></ThemeProvider>);
