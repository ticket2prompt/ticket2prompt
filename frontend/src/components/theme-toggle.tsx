import { RiSunLine, RiMoonLine, RiComputerLine } from "@remixicon/react"
import { Button } from "@/components/ui/button"
import { useTheme } from "@/components/theme-provider"

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()

  const cycle = () => {
    if (theme === "light") setTheme("dark")
    else if (theme === "dark") setTheme("system")
    else setTheme("light")
  }

  return (
    <Button variant="ghost" size="icon" onClick={cycle} className="h-8 w-8 text-muted-foreground hover:text-foreground transition-colors">
      {theme === "light" && <RiSunLine className="h-4 w-4" />}
      {theme === "dark" && <RiMoonLine className="h-4 w-4" />}
      {theme === "system" && <RiComputerLine className="h-4 w-4" />}
      <span className="sr-only">Toggle theme</span>
    </Button>
  )
}
