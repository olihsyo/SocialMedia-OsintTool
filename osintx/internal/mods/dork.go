package mods

import "fmt"

func Dorks(target, kind string) []string {
	if kind == "email" {
		return []string{
			fmt.Sprintf(`"%s"`, target),
			fmt.Sprintf(`"%s" filetype:pdf`, target),
			fmt.Sprintf(`"%s" (password OR passwd OR credentials)`, target),
			fmt.Sprintf(`site:pastebin.com "%s"`, target),
			fmt.Sprintf(`site:github.com "%s"`, target),
			fmt.Sprintf(`site:trello.com "%s"`, target),
		}
	}
	return []string{
		fmt.Sprintf(`"%s"`, target),
		fmt.Sprintf(`"%s" (contact OR whatsapp OR telegram)`, target),
		fmt.Sprintf(`"%s" filetype:pdf`, target),
		fmt.Sprintf(`site:facebook.com "%s"`, target),
		fmt.Sprintf(`site:linkedin.com "%s"`, target),
	}
}
