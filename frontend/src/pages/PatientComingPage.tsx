import {
  HeartPulse,
} from "lucide-react";

export default function PatientComingPage({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="patient-empty-state">
      <HeartPulse />

      <h2>
        {title}
      </h2>

      <p>
        {description}
      </p>
    </div>
  );
}
