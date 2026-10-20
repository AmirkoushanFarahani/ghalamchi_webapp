import { createRoot } from "react-dom/client";
import { FourSectionStudentRegistrationForm } from "../src/pages/SchoolPages";
import { ThemeProvider } from "../src/theme/ThemeContext";
createRoot(document.getElementById("root")!).render(<ThemeProvider><FourSectionStudentRegistrationForm close={() => {}} saved={() => { document.body.dataset.saved = "true"; }} /></ThemeProvider>);
