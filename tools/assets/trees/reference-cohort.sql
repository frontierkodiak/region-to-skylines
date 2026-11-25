-- Candidate references only: whole-crown/mask QA is required before shape fitting.
-- Cabinet adds the frozen observer-v1 train/val/test split after selection.
WITH labelled AS (
  SELECT p.*, CASE
    WHEN {{subtree:48498:p}} THEN 'Gleditsia'
    WHEN {{subtree:54856:p}} THEN 'Tilia'
    WHEN {{subtree:53549:p}} THEN 'Ulmus'
  END AS genus
  FROM photos p
  WHERE ({{subtree:48498:p}} OR {{subtree:54856:p}} OR {{subtree:53549:p}})
    AND p.quality_grade = 'research'
    AND lower(p.license) IN ('cc0', 'cc-by', 'cc-by-sa')
    AND p.width >= 640 AND p.height >= 640
    AND p.observer_id IS NOT NULL
), independent AS (
  SELECT * EXCLUDE (observer_row) FROM (
    SELECT *, row_number() OVER (
      PARTITION BY genus, observer_id ORDER BY sha256(CAST(photo_id AS VARCHAR))
    ) AS observer_row FROM labelled
  ) WHERE observer_row = 1
)
SELECT * EXCLUDE (genus_row) FROM (
  SELECT *, row_number() OVER (
    PARTITION BY genus ORDER BY sha256(CAST(photo_id AS VARCHAR))
  ) AS genus_row FROM independent
) WHERE genus_row <= 32
