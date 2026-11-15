package engine

import (
	"os"

	"gopkg.in/yaml.v3"
)

type Site struct {
	Name     string            `yaml:"name"`
	Kinds    []string          `yaml:"kinds"`
	URL      string            `yaml:"url"`
	Method   string            `yaml:"method"`
	Body     string            `yaml:"body"`
	Headers  map[string]string `yaml:"headers"`
	Type     string            `yaml:"type"`
	Expect   string            `yaml:"expect"`
	Weight   int               `yaml:"weight"`
	Note     string            `yaml:"note"`
	Disabled bool              `yaml:"disabled"`
}

func LoadRegistry(path string) ([]Site, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var out []Site
	if err := yaml.Unmarshal(raw, &out); err != nil {
		return nil, err
	}
	keep := out[:0]
	for _, s := range out {
		if s.Disabled || s.URL == "" {
			continue
		}
		if s.Method == "" {
			s.Method = "GET"
		}
		if s.Weight == 0 {
			s.Weight = 3
		}
		keep = append(keep, s)
	}
	return keep, nil
}
