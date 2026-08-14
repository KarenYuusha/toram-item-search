from __future__ import annotations

class HelpService:
    SYNTAX = (
        "Search syntax:\n"
        "- Item: venena\n"
        "- Stat: cr xtal\n"
        "- Numeric: hp >= 5000 armor\n"
        "- Boolean: hp > 5000 and cr bow\n"
        "- Negative: -aggro xtal\n"
        "- Ranking: highest cr / lowest mp."
    )
    def answer_direct(self,text:str)->str|None:
        q=' '.join(text.casefold().strip(' ?!.').split())
        if q in {'help','help me','how to use','how do i use it','how to search','how do i search','search help','search syntax','usage'}:
            return self.SYNTAX
        return None
