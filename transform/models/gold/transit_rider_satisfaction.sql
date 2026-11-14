{#
  gold.transit_rider_satisfaction — one row per survey × question

  What riders tell the MBTA's monthly survey (decision 0019): each question's
  answers grouped into positive (the top three of seven: satisfied, or
  agreeing), neutral, and negative, as shares of respondents. Published
  shares are rounded, so the three sum to within a couple of points of 1.

  Steps:
    1. final select — each question with a short label and its three shares
#}

-- 1. A label says what a positive answer means, so a chart needs no legend.
SELECT
    survey_month,
    CASE question
        WHEN 'How would you rate the mbta overall?' THEN 'Satisfied with the MBTA overall'
        WHEN 'The mbta provides reliable public transportation services.' THEN 'Agree the MBTA is reliable'
        WHEN 'How would you rate your most recent trip?' THEN 'Satisfied with their last trip'
        WHEN "How satisfied are you with the MBTA's communication overall?" THEN 'Satisfied with its communication'
        ELSE question
    END                                                         AS question_label,
    question,
    respondents,
    answer_5_share + answer_6_share + answer_7_share            AS positive_share,
    answer_4_share                                              AS neutral_share,
    answer_1_share + answer_2_share + answer_3_share            AS negative_share,
    ingested_at
FROM {{ ref('mbta_customer_satisfaction__base') }}
