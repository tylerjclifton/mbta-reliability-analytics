{#
  silver.mbta_customer_satisfaction__base — one row per survey × question

  The MBTA's monthly rider survey, as of the latest pull, in project
  conventions (decision 0019): every run re-pulls the whole file, so keeping
  the latest lets revisions win. Each question has seven answers, in order
  from most negative to most positive (tested in _silver__models.yml), each
  with the share of respondents giving it.

  Steps:
    1. latest_versions — latest pull per survey × question
    2. final select    — renamed and typed
#}

WITH

    -- 1. Latest pull per survey × question.
    latest_versions AS (
        SELECT *
        FROM {{ source('bronze', 'mbta_customer_satisfaction') }}
        {{ keep_latest_version(['survey_date', 'question_description']) }}
    )

-- 2. Project conventions.
SELECT
    survey_date                 AS survey_month,
    question_description        AS question,
    response_total              AS respondents,
    response_1_text             AS answer_1,
    response_1_percent          AS answer_1_share,
    response_2_text             AS answer_2,
    response_2_percent          AS answer_2_share,
    response_3_text             AS answer_3,
    response_3_percent          AS answer_3_share,
    response_4_text             AS answer_4,
    response_4_percent          AS answer_4_share,
    response_5_text             AS answer_5,
    response_5_percent          AS answer_5_share,
    response_6_text             AS answer_6,
    response_6_percent          AS answer_6_share,
    response_7_text             AS answer_7,
    response_7_percent          AS answer_7_share,
    ingested_at,
    ingested_by
FROM latest_versions
