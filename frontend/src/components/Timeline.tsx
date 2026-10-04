import type { Event } from "../contracts";
export function Timeline({
  events,
  onEvidence,
}: {
  events: Event[];
  onEvidence: (id: string) => void;
}) {
  return (
    <section className="card timeline">
      <div className="row spread">
        <h3>Observation timeline</h3>
        <span className="muted">{events.length} moments</span>
      </div>
      {events.length === 0 ? (
        <p className="empty">
          Your review moments and answers will appear here. Give recording
          consent to start.
        </p>
      ) : (
        <ol>
          {events
            .slice(-12)
            .reverse()
            .map((event) => (
              <li key={event.event_id}>
                <button
                  className="timeline-item"
                  onClick={() => onEvidence(event.event_id)}
                >
                  <span className="timeline-dot" />
                  <span>
                    <span className="row">
                      <strong>{event.event_type.replaceAll("_", " ")}</strong>
                      <span className="badge neutral">{event.source}</span>
                    </span>
                    <span className="timeline-excerpt">
                      {String(
                        event.payload.text ??
                          event.payload.question ??
                          event.payload.summary ??
                          event.payload.reason ??
                          event.payload.case_id ??
                          "Stored review evidence",
                      )}
                    </span>
                  </span>
                  <time>
                    {new Date(event.timestamp).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </time>
                </button>
              </li>
            ))}
        </ol>
      )}
    </section>
  );
}
