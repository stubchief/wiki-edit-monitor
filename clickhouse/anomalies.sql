WITH hourly AS (
    SELECT
        toStartOfHour(tick_start) AS hour,
        wiki,
        server_name,
        namespace,
        title,
        sum(edit_count) AS edit_count
    FROM agg_edits
    GROUP BY hour, wiki, server_name, namespace, title
),
scored AS (
    SELECT
        hour,
        wiki,
        server_name,
        namespace,
        title,
        edit_count,
        avgIf(edit_count, hour < (SELECT max(hour) FROM hourly))
            OVER (PARTITION BY wiki, title) AS baseline,
        stddevPopIf(edit_count, hour < (SELECT max(hour) FROM hourly))
            OVER (PARTITION BY wiki, title) AS stddev,
        count() OVER (PARTITION BY wiki, title) AS observation_count
    FROM hourly
)
SELECT
    hour,
    wiki,
    server_name,
    namespace,
    title,
    edit_count,
    round(baseline, 2) AS baseline,
    round(stddev, 2)   AS stddev,
    round((edit_count - baseline) / stddev, 2) AS z_score
FROM scored
WHERE hour = (SELECT max(hour) FROM hourly)
  AND observation_count >= 10
  AND stddev > 0
  AND z_score > 0
ORDER BY z_score DESC
LIMIT 50