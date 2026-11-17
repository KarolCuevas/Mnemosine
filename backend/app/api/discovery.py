"""Descubrimiento y biblioteca pública (Fase 4).

PUBLIC significa accesible para las cuentas autenticadas del sistema: todo
este módulo exige sesión y solo expone copias PUBLIC y disponibles.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.schemas.discovery import DiscoveryAccount, DiscoveryCatalog, DiscoveryItem, SharedItem
from app.security.deps import CurrentUser, get_current_user
from app.services import discovery, library

router = APIRouter(tags=["Descubrimiento"])


class DiscoveryAccountsOut(BaseModel):
    accounts: list[DiscoveryAccount]


class SharedItemsOut(BaseModel):
    items: list[SharedItem]


@router.get("/discovery", response_model=DiscoveryAccountsOut)
def list_discovery(current: CurrentUser = Depends(get_current_user)) -> DiscoveryAccountsOut:
    accounts = [DiscoveryAccount(**row) for row in discovery.accounts_with_public_copies()]
    return DiscoveryAccountsOut(accounts=accounts)


@router.get("/discovery/{username}", response_model=DiscoveryCatalog)
def get_public_catalog(username: str, current: CurrentUser = Depends(get_current_user)) -> DiscoveryCatalog:
    catalog = discovery.public_catalog(username=username)
    if catalog is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No encontrado")
    return DiscoveryCatalog(
        username=catalog["username"],
        display_name=catalog["display_name"],
        items=[DiscoveryItem(**item) for item in catalog["items"]],
    )


@router.get("/library/shared", response_model=SharedItemsOut)
def list_shared_with_me(current: CurrentUser = Depends(get_current_user)) -> SharedItemsOut:
    items = [SharedItem(**row) for row in library.list_shared_with_me(user_id=current.user_id)]
    return SharedItemsOut(items=items)
