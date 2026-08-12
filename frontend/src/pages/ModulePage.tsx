interface ModulePageProps {
  title: string;
  description: string;
}

export default function ModulePage({
  title,
  description,
}: ModulePageProps) {
  return (
    <div className="module-page">
      <p className="eyebrow">
        MODULE HOSPITALIER
      </p>

      <h1>{title}</h1>

      <p className="subtitle">
        {description}
      </p>

      <div className="coming-panel">
        <h2>
          Interface en préparation
        </h2>

        <p>
          Ce module sera connecté au
          microservice gRPC correspondant.
        </p>
      </div>
    </div>
  );
}
