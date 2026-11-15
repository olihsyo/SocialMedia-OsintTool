package mods

import (
	"context"
	"strings"

	"github.com/nyaruka/phonenumbers"
)

func PhoneIntel(ctx context.Context, raw string, verbose bool) *Intel {
	i := &Intel{Kind: "phone"}
	num, err := phonenumbers.Parse(raw, "")
	if err != nil || !phonenumbers.IsValidNumber(num) {
		i.ValidNumber = false
		i.Notes = append(i.Notes, "number did not parse as valid")
		return i
	}
	i.ValidNumber = true
	i.E164 = phonenumbers.Format(num, phonenumbers.E164)
	i.National = phonenumbers.Format(num, phonenumbers.NATIONAL)
	i.Region = phonenumbers.GetRegionCodeForNumber(num)

	// FIX: ২টি ভ্যালু রিটার্ন করে (string, error)
	carrier, err := phonenumbers.GetCarrierForNumber(num, "en")
	if err == nil {
		i.Carrier = carrier
	}
	
	i.LineType = lineType(num)

	// FIX: ২টি ভ্যালু রিটার্ন করে ([]string, error)
	timezones, err := phonenumbers.GetTimezonesForNumber(num)
	if err == nil {
		i.Timezones = timezones
	}

	// FIX: GetGeocodingForNumber এখন (string, error) রিটার্ন করে
	geo, err := phonenumbers.GetGeocodingForNumber(num, "en")
	if err == nil && geo != "" {
		i.Notes = append(i.Notes, "geo: "+geo)
	}
	
	return i
}

func lineType(n *phonenumbers.PhoneNumber) string {
	switch phonenumbers.GetNumberType(n) {
	case phonenumbers.MOBILE:
		return "mobile"
	case phonenumbers.FIXED_LINE:
		return "fixed"
	case phonenumbers.FIXED_LINE_OR_MOBILE:
		return "fixed_or_mobile"
	case phonenumbers.VOIP:
		return "voip"
	case phonenumbers.TOLL_FREE:
		return "toll_free"
	default:
		return "unknown"
	}
}

func Digits(e164 string) string { return strings.TrimPrefix(e164, "+") }
