{{
	config(
		schema='nws',
		alias='silver',
		unique_key=['observation_id']
	)
}}

{{ build_silver_merge('nws') }}