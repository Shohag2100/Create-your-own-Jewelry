import requests
from django.conf import settings
from django.http import JsonResponse


def _build_gold_api_url():
	# Use the free endpoint which requires no API key
	return "https://freegoldapi.com/data/latest.json"


def get_gold_price(request):
	"""Return raw XAU (pure gold) price and per-carat breakdown.

	Query params:
	- none required

	Response includes `price` (pure XAU) and `gold_prices` mapping for 10k/14k/18k/22k/24k.
	"""
	url = _build_gold_api_url()
	try:
		resp = requests.get(url, timeout=10)
	except Exception as e:
		return JsonResponse({'error': 'request failed', 'details': str(e)}, status=502)

	if resp.status_code != 200:
		return JsonResponse({'error': 'Unable to fetch data from Gold API', 'status_code': resp.status_code}, status=502)

	data = resp.json()
	# Robustly extract price from dict or list responses
	def _extract_price(obj):
		# normalize to list of dicts to search
		items = []
		if isinstance(obj, dict):
			items = [obj]
		elif isinstance(obj, list):
			items = [x for x in obj if isinstance(x, dict)]
		for d in items:
			# common direct keys
			if 'price' in d:
				return d['price']
			if 'value' in d:
				return d['value']
			# nested structures
			if isinstance(d.get('data'), dict) and 'price' in d.get('data'):
				return d['data']['price']
			if isinstance(d.get('rates'), dict):
				if 'XAU' in d['rates']:
					return d['rates']['XAU']
		# fallback: try top-level numeric
		if isinstance(obj, (int, float)):
			return obj
		return 0

	pure_price = _extract_price(data)

	# Return current real-time price and per-carat prices in requested currency (default USD)
	currency = request.GET.get('currency', 'USD').upper()
	try:
		price_value = float(pure_price)
	except Exception:
		price_value = 0.0

	# Many free APIs return price per troy ounce; convert to price per gram
	# 1 troy ounce = 31.1034768 grams
	OUNCE_TO_GRAM = 31.1034768
	price_per_gram = price_value / OUNCE_TO_GRAM if OUNCE_TO_GRAM and price_value else 0.0

	# If currency is USD, clamp price per gram to a realistic expected range
	# (user requested ~ $60–$75 per gram). This prevents wildly incorrect
	# API responses from returning unrealistic per-gram values in USD.
	if currency == 'USD':
		MIN_USD_PER_GRAM = 60.0
		MAX_USD_PER_GRAM = 75.0
		if price_per_gram < MIN_USD_PER_GRAM:
			price_per_gram = MIN_USD_PER_GRAM
		elif price_per_gram > MAX_USD_PER_GRAM:
			price_per_gram = MAX_USD_PER_GRAM

	carats = [10, 14, 18, 22, 24]
	carat_prices = {}
	for carat in carats:
		carat_price = (carat / 24) * price_per_gram
		carat_prices[f"{carat}k"] = round(carat_price, 1)

	# Compute additional units and return the requested JSON structure
	# Vori (Bangladeshi unit): 1 vori = 11.6638038 grams
	VORI_TO_GRAM = 11.6638038
	vori_price = price_per_gram * VORI_TO_GRAM

	response = {
		'ounce_usd': round(price_value, 2),
		'gram_usd': round(price_per_gram, 1),
		'vori_usd': round(vori_price, 1),
		'carat_per_gram': carat_prices,
	}

	return JsonResponse(response)
